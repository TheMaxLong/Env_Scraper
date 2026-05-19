"""Anthropic Claude vision call + raw-text parser.

One single API call per extract. No retries, no chaining. Buyers pay tokens.
"""
from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = APP_ROOT / "prompts"

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_MAX_WIDTH = 900
DEFAULT_JPEG_QUALITY = 78


@dataclass
class ImagePayload:
    """A single image ready for the API. base64 is raw (no data: prefix)."""
    name: str
    base64: str
    media_type: str   # "image/jpeg" or "image/png"


@dataclass
class RoomReading:
    """One parsed environmental row. Optional fields default to None."""
    room: str
    day: Optional[int] = None
    IN_pH: Optional[float] = None
    IN_EC: Optional[float] = None
    IN_VWC: Optional[float] = None
    IN_solus: Optional[float] = None
    S1_pH: Optional[float] = None
    S1_EC: Optional[float] = None
    S1_VWC: Optional[float] = None
    S1_solus: Optional[float] = None
    S2_pH: Optional[float] = None
    S2_EC: Optional[float] = None
    S2_VWC: Optional[float] = None
    S2_solus: Optional[float] = None
    S3_pH: Optional[float] = None
    S3_EC: Optional[float] = None
    S3_VWC: Optional[float] = None
    S3_solus: Optional[float] = None
    S4_pH: Optional[float] = None
    S4_EC: Optional[float] = None
    S4_VWC: Optional[float] = None
    S4_solus: Optional[float] = None
    S5_pH: Optional[float] = None
    S5_EC: Optional[float] = None
    S5_VWC: Optional[float] = None
    S5_solus: Optional[float] = None
    temp: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[int] = None
    notes: str = ""
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionResult:
    """End-to-end result of one extraction."""
    raw_text: str
    rows: List[RoomReading]
    model: str
    source_images: List[str]
    building: Optional[str] = None
    room_override: Optional[str] = None


def compress_image(file_bytes: bytes, max_width: int, jpeg_quality: int) -> ImagePayload:
    """Downscale + JPEG-compress an uploaded image for the API.

    Mirrors the React toCompressedBase64 logic. Saves tokens at the buyer's cost.
    """
    from PIL import Image
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if img.width > max_width:
        scale = max_width / img.width
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return ImagePayload(name="uploaded.jpg", base64=b64, media_type="image/jpeg")


def render_system_prompt(config: Dict[str, Any]) -> str:
    """Render the Jinja2 system prompt from the facility config."""
    # Imported lazily so the parser/exporter modules don't require jinja2 to import.
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(PROMPT_DIR)),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("extract_system.j2")
    facility = config["facility"]
    return template.render(
        facility=facility,
        thresholds=facility["thresholds"],
        exclude_keywords=facility.get("exclude_keywords", []),
        solus_ec_enabled=bool(facility.get("solus_ec_enabled", False)),
    )


def call_claude(
    images: List[ImagePayload],
    system_prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    room_override: Optional[str] = None,
) -> str:
    """Make a single vision call. Returns the raw text output.

    Raises a helpful exception on auth / network errors so the UI can surface them.
    """
    # Imported lazily so the app can still launch with a stale install.
    import anthropic

    if not api_key or not api_key.strip():
        raise ValueError(
            "No Anthropic API key set. Open the Settings tab and paste your key. "
            "Get one at https://console.anthropic.com/settings/keys."
        )

    client = anthropic.Anthropic(api_key=api_key.strip())

    context_note = (
        f"User context: This image is from room {room_override.strip().upper()}. "
        "Use this as the Room ID."
        if room_override and room_override.strip()
        else "Map zone names using the lookup table. If room ID cannot be determined, use [?]."
    )

    content: List[Dict[str, Any]] = []
    for img in images:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.media_type,
                    "data": img.base64,
                },
            }
        )
    content.append(
        {
            "type": "text",
            "text": context_note + "\n\nExtract all environmental data from these images.",
        }
    )

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )

    return "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    )


# ---------------------------------------------------------------------------
# Parser: turn the model's plain-text output into structured rows.
# ---------------------------------------------------------------------------

# Head of a runoff line: ROOM | DAY |
_LINE_HEAD = re.compile(
    r"^(?P<room>[A-Z]{2}\d+)\s*\|\s*(?P<day>\d+|D\d+|\?)\s*\|(?P<rest>.+)$",
    re.IGNORECASE,
)

# Station header inside a line: "IN:" or "S1:" etc.
_STATION_LABEL = re.compile(r"^(IN|S\d+):\s*(.+)$", re.IGNORECASE)

# Bracketed [pH/EC] payload — pH on left, EC on right, supports '?' / '--' / 'N/A'.
_PH_EC_BRACKET = re.compile(r"\[([^\]]+)\]")

# Optional VWC suffix: (vwc:42%) or (vwc:42.5%)
_VWC_SUFFIX = re.compile(r"vwc:\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)

# Optional Solus suffix: (sec:3.25)
_SEC_SUFFIX = re.compile(r"sec:\s*(\d+\.\d+)", re.IGNORECASE)

# Tail fields: Temp / Hum / CO2.
_TEMP_RE = re.compile(r"Temp:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_HUM_RE = re.compile(r"Hum:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_CO2_RE = re.compile(r"CO2:\s*(\d+)", re.IGNORECASE)

# Legacy fallback — old "- EF1 — 70° // 67.5% // 1030 ppm" environmental lines.
_ENV_LEGACY = re.compile(
    r"^-?\s*(?P<room>[A-Z]{2}\d+)(?:\s+\([^)]+\))?\s+[—\-]+\s+"
    r"(?P<temp>[\d.]+)°\s*//\s*(?P<hum>[\d.]+)%\s*//\s*(?P<co2>\d+)\s*ppm",
    re.IGNORECASE,
)


def _maybe_float(s: Any) -> Optional[float]:
    """Coerce a numeric-ish string to float. Returns None for '?', '--', 'N/A', empties."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    text = str(s).strip()
    if not text or text.upper() in ("N/A", "NA", "--", "?"):
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text)
    if not cleaned or cleaned in (".", "-"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_station_payload(payload: str) -> Dict[str, Optional[float]]:
    """Parse '[6.4/3.6](vwc:34%,sec:5.37)' into {pH, EC, VWC, solus}."""
    out: Dict[str, Optional[float]] = {"pH": None, "EC": None, "VWC": None, "solus": None}

    bracket = _PH_EC_BRACKET.search(payload)
    if bracket:
        inner = bracket.group(1)
        if inner.upper() in ("N/A", "NA"):
            return out
        if "/" in inner:
            ph_part, ec_part = inner.split("/", 1)
            out["pH"] = _maybe_float(ph_part)
            out["EC"] = _maybe_float(ec_part)

    vwc_m = _VWC_SUFFIX.search(payload)
    if vwc_m:
        out["VWC"] = _maybe_float(vwc_m.group(1))

    sec_m = _SEC_SUFFIX.search(payload)
    if sec_m:
        out["solus"] = _maybe_float(sec_m.group(1))

    return out


def _parse_runoff_line(line: str) -> Optional[RoomReading]:
    """Parse one '<ROOM> | <DAY> | IN: [..] // S1: [..] // ...' line."""
    head = _LINE_HEAD.match(line.strip())
    if not head:
        return None

    room = head.group("room").upper()
    day_raw = head.group("day")
    rest = head.group("rest")

    day: Optional[int] = None
    if day_raw and day_raw != "?":
        try:
            day = int(day_raw.lstrip("Dd"))
        except ValueError:
            day = None

    reading = RoomReading(room=room, day=day)

    # Walk the segments split on " // ".
    segments = [s.strip() for s in rest.split("//")]
    for seg in segments:
        if not seg:
            continue

        station_m = _STATION_LABEL.match(seg)
        if station_m:
            label = station_m.group(1).upper()
            payload = station_m.group(2)
            parsed = _parse_station_payload(payload)
            for field_name, value in parsed.items():
                attr = f"{label}_{field_name}"
                if hasattr(reading, attr):
                    setattr(reading, attr, value)
            continue

        m = _TEMP_RE.search(seg)
        if m:
            reading.temp = _maybe_float(m.group(1))
            continue
        m = _HUM_RE.search(seg)
        if m:
            reading.humidity = _maybe_float(m.group(1))
            continue
        m = _CO2_RE.search(seg)
        if m:
            try:
                reading.co2 = int(m.group(1))
            except ValueError:
                pass
            continue

    return reading


def parse_output(text: str) -> List[RoomReading]:
    """Parse the model's raw text into RoomReading objects.

    Primary path: 'ROOM | DAY | IN: [pH/EC](vwc..sec..) // S1: [..] // ...' lines.
    Legacy fallback: '- ROOM — TEMP° // HUM% // CO2 ppm' environmental-only lines.
    Unknown lines are dropped.
    """
    rows: List[RoomReading] = []
    seen_rooms: Dict[str, int] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        reading = _parse_runoff_line(line)
        if reading is not None:
            # Dedupe: last-write-wins on room, preserves order of first sighting.
            if reading.room in seen_rooms:
                rows[seen_rooms[reading.room]] = reading
            else:
                seen_rooms[reading.room] = len(rows)
                rows.append(reading)
            continue

        legacy = _ENV_LEGACY.search(line)
        if legacy:
            room = legacy.group("room").upper()
            r = RoomReading(
                room=room,
                temp=_maybe_float(legacy.group("temp")),
                humidity=_maybe_float(legacy.group("hum")),
                co2=int(legacy.group("co2")),
            )
            if room in seen_rooms:
                rows[seen_rooms[room]] = r
            else:
                seen_rooms[room] = len(rows)
                rows.append(r)

    return rows


def extract(
    image_payloads: List[ImagePayload],
    config: Dict[str, Any],
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    building: Optional[str] = None,
    room_override: Optional[str] = None,
) -> ExtractionResult:
    """Top-level extraction. One Anthropic call, then parse the result."""
    system_prompt = render_system_prompt(config)
    raw_text = call_claude(
        images=image_payloads,
        system_prompt=system_prompt,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        room_override=room_override,
    )
    rows = parse_output(raw_text)
    return ExtractionResult(
        raw_text=raw_text,
        rows=rows,
        model=model,
        source_images=[img.name for img in image_payloads],
        building=building,
        room_override=room_override,
    )
