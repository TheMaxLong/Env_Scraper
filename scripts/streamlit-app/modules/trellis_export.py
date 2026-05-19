"""Push extracted readings to a Trellis dashboard via POST /api/readings/bulk.

Trellis is the operator-side observability companion to Runoff Reader. Once a
user extracts and edits their log sheet, this module ships the cleaned readings
to their Trellis instance in a single HTTP call.

Design notes:
- Stdlib + `requests` only. No new dependencies.
- The Extract tab produces rows shaped like Runoff Reader's RoomReading
  (one row per room, with IN + S1..S5 stations bundled side-by-side).
  Trellis expects one record PER STATION, so we expand each row into up to
  6 station records (IN, S1, S2, S3, S4, S5).
- A station record is only emitted if it has at least one of pH / EC / VWC.
- Rows missing a `room` field are skipped and reported in the result.
- Errors are caught and surfaced via the return dict — never raised — so the
  UI can show a friendly red message without a traceback.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests

# Stations to expand per row. Matches the RoomReading dataclass fields.
_STATION_PREFIXES = ("IN", "S1", "S2", "S3", "S4", "S5")

# Per-Trellis-API contract; the schema caps stationLabel at 8 chars.
_MAX_STATION_LABEL = 8

# Source tag for analytics on the Trellis side.
_SOURCE_TAG = "runoff_reader_ocr"


def _coerce_number(value: Any) -> Optional[float]:
    """Return a float or None. Treats blanks, NaN, '?', '--' as None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        # NaN check without numpy.
        if value != value:  # noqa: PLR0124
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.upper() in ("?", "--", "N/A", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(value: Any) -> Optional[int]:
    """Like _coerce_number but returns int for fields like CO2."""
    f = _coerce_number(value)
    if f is None:
        return None
    return int(f)


def _now_iso_z() -> str:
    """ISO8601 UTC timestamp with Z suffix — the shape Trellis Zod expects."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_recorded_at(value: Any) -> Optional[str]:
    """Pass through ISO strings; otherwise return None (caller will default)."""
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    text = str(value).strip()
    return text or None


def _build_station_records(
    row: Dict[str, Any],
    *,
    default_recorded_at: str,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    """Expand one row into per-station Trellis records.

    Returns an empty list if the row lacks a room code or has no measurable
    stations.
    """
    room_raw = row.get("room") or row.get("roomCode")
    if not room_raw:
        logger.warning("skipping row with no room code: %r", row)
        return []
    room_code = str(room_raw).strip().upper()
    if not room_code:
        logger.warning("skipping row with empty room code: %r", row)
        return []

    recorded_at = (
        _normalize_recorded_at(row.get("recordedAt"))
        or _normalize_recorded_at(row.get("recorded_at"))
        or default_recorded_at
    )

    day_raw = row.get("day")
    day_number: Optional[int]
    if isinstance(day_raw, bool):
        day_number = None
    elif isinstance(day_raw, (int, float)) and day_raw == day_raw:  # NaN guard
        day_number = int(day_raw)
    elif isinstance(day_raw, str) and day_raw.strip().isdigit():
        day_number = int(day_raw.strip())
    else:
        day_number = None

    temp = _coerce_number(row.get("temp") or row.get("temperature"))
    humidity = _coerce_number(row.get("humidity"))
    co2 = _coerce_int(row.get("co2"))
    notes = row.get("notes")
    if notes is not None and not isinstance(notes, str):
        notes = str(notes)

    records: List[Dict[str, Any]] = []
    env_attached = False  # Only tag temp/humidity/co2 on the first station to avoid duplicate metrics.
    for prefix in _STATION_PREFIXES:
        ph = _coerce_number(row.get(f"{prefix}_pH"))
        ec = _coerce_number(row.get(f"{prefix}_EC"))
        vwc = _coerce_number(row.get(f"{prefix}_VWC"))
        solus = _coerce_number(row.get(f"{prefix}_solus"))

        if ph is None and ec is None and vwc is None and solus is None:
            continue

        rec: Dict[str, Any] = {
            "roomCode": room_code,
            "stationLabel": prefix[:_MAX_STATION_LABEL],
            "source": _SOURCE_TAG,
            "recordedAt": recorded_at,
        }
        if day_number is not None:
            rec["dayNumber"] = day_number
        if ph is not None:
            rec["ph"] = ph
        if ec is not None:
            rec["ec"] = ec
        if vwc is not None:
            rec["vwc"] = vwc
        if solus is not None:
            rec["solusEc"] = solus
        if not env_attached:
            if temp is not None:
                rec["temperature"] = temp
            if humidity is not None:
                rec["humidity"] = humidity
            if co2 is not None:
                rec["co2"] = co2
            if notes:
                rec["notes"] = notes
            env_attached = True

        records.append(rec)

    if not records:
        logger.warning("row had room=%s but no station data; skipped", room_code)
    return records


def export_to_trellis(
    readings: Iterable[Dict[str, Any]],
    *,
    trellis_url: str,
    auto_create_rooms: bool = True,
    timeout_s: float = 10.0,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """POST extracted readings to a Trellis instance.

    Args:
        readings: an iterable of dicts shaped like Runoff Reader rows
            (room, day, IN_pH, IN_EC, ..., S5_solus, temp, humidity, co2, notes).
            Anything missing required fields (room code or any station value)
            is reported in the `skipped` field of the return dict.
        trellis_url: base URL of the Trellis API server (no trailing /api).
            e.g. "http://localhost:5050". Bulk endpoint is appended.
        auto_create_rooms: pass-through to Trellis. When True, unknown room
            codes are created on the fly.
        timeout_s: HTTP timeout for the bulk POST.
        logger: optional logger for warnings on skipped rows.

    Returns:
        {
            "ok": bool,
            "status": int,            # HTTP status, 0 on transport error
            "response": dict | None,  # parsed JSON body if available
            "error": str | None,      # human-readable error if !ok
            "skipped": list[dict],    # rows we didn't send + a `reason`
        }
    """
    log = logger or logging.getLogger("runoff_reader.trellis_export")

    if not trellis_url or not isinstance(trellis_url, str):
        return {
            "ok": False,
            "status": 0,
            "response": None,
            "error": "Trellis URL is not configured. Set it in the Settings tab.",
            "skipped": [],
        }
    base = trellis_url.strip().rstrip("/")
    if not (base.startswith("http://") or base.startswith("https://")):
        return {
            "ok": False,
            "status": 0,
            "response": None,
            "error": "Trellis URL must start with http:// or https://.",
            "skipped": [],
        }

    default_recorded_at = _now_iso_z()
    body_readings: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for row in readings:
        if not isinstance(row, dict):
            skipped.append({"row": row, "reason": "row was not a dict"})
            continue
        station_records = _build_station_records(
            row, default_recorded_at=default_recorded_at, logger=log
        )
        if not station_records:
            skipped.append(
                {"row": row, "reason": "no room code or no station readings"}
            )
            continue
        body_readings.extend(station_records)

    if not body_readings:
        return {
            "ok": False,
            "status": 0,
            "response": None,
            "error": "Nothing to send — every row was missing a room code or station data.",
            "skipped": skipped,
        }

    payload = {
        "autoCreateRooms": bool(auto_create_rooms),
        "readings": body_readings,
    }

    url = f"{base}/api/readings/bulk"
    try:
        resp = requests.post(url, json=payload, timeout=timeout_s)
    except requests.exceptions.ConnectionError as e:
        return {
            "ok": False,
            "status": 0,
            "response": None,
            "error": f"Could not reach Trellis at {url}. Is it running? ({e})",
            "skipped": skipped,
        }
    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "status": 0,
            "response": None,
            "error": f"Trellis did not respond within {timeout_s:g}s.",
            "skipped": skipped,
        }
    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "status": 0,
            "response": None,
            "error": f"Request failed: {e}",
            "skipped": skipped,
        }

    body: Optional[Dict[str, Any]]
    try:
        body = resp.json() if resp.content else None
    except ValueError:
        body = None

    if 200 <= resp.status_code < 300:
        return {
            "ok": True,
            "status": resp.status_code,
            "response": body,
            "error": None,
            "skipped": skipped,
        }

    err_msg: str
    if isinstance(body, dict) and body.get("error"):
        err_msg = f"Trellis rejected the export: {body['error']}"
    else:
        err_msg = f"Trellis returned HTTP {resp.status_code}."
    return {
        "ok": False,
        "status": resp.status_code,
        "response": body,
        "error": err_msg,
        "skipped": skipped,
    }
