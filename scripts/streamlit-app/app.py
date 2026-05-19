"""Runoff Reader — by hark.equipment.

Single-file UI. Four tabs: Extract / Configure / History / Settings.
First-run wizard fires when config/facility.yaml is missing.

Run with:
    streamlit run app.py
or double-click scripts/run.command (Mac) / scripts/run.bat (Windows).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
import yaml
from PIL import Image

from modules import config_loader, credentials, exporters, extraction, history
from modules.extraction import ImagePayload
from modules.trellis_export import export_to_trellis

APP_ROOT = Path(__file__).resolve().parent
SAMPLE_IMAGE = APP_ROOT / "assets" / "sample_log.png"

st.set_page_config(
    page_title="Runoff Reader — hark.equipment",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get help": "mailto:max@hark.equipment",
        "Report a bug": "mailto:max@hark.equipment?subject=Runoff%20Reader%20bug",
        "About": "Runoff Reader — by hark.equipment. Built by an active cultivation operator. Visit hark.equipment.",
    },
)

st.markdown(
    """
    <style>
      #MainMenu {visibility: hidden;}
      header [data-testid="stToolbar"] {visibility: hidden;}
      footer {visibility: hidden;}
      footer:after {content: '';}
      .stDeployButton {display: none;}
      [data-testid="stStatusWidget"] {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div style="padding: 0.25rem 0 1.25rem 0; border-bottom: 1px solid #d8d4c8; margin-bottom: 1.5rem;">
      <div style="font-size: 1.6rem; font-weight: 600; color: #1f3a2e; letter-spacing: -0.01em;">Runoff Reader</div>
      <div style="font-size: 0.85rem; color: #5a5a5a; margin-top: -0.1rem;">by hark.equipment &mdash; tools for the trade</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
def _init_state() -> None:
    """Set up Streamlit session state with safe defaults."""
    defaults: Dict[str, Any] = {
        "wizard_step": 0,
        "wizard_complete": config_loader.config_exists(),
        "last_result": None,
        "api_key": credentials.load_api_key() or "",
        "model": extraction.DEFAULT_MODEL,
        "max_width": extraction.DEFAULT_MAX_WIDTH,
        "jpeg_quality": extraction.DEFAULT_JPEG_QUALITY,
        "uploaded_images": [],
        "trellis_url": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ---------------------------------------------------------------------------
# Config & helpers
# ---------------------------------------------------------------------------
def _load_cfg() -> Dict[str, Any]:
    """Cached-ish config load. Re-reads if user just saved."""
    try:
        return config_loader.load_config()
    except FileNotFoundError:
        st.session_state.wizard_complete = False
        return {}


def _building_codes(cfg: Dict[str, Any]) -> List[str]:
    return config_loader.list_buildings(cfg) if cfg else []


def _friendly_error(prefix: str, err: Exception) -> str:
    """Translate exceptions into grower-readable text."""
    msg = str(err)
    if "401" in msg or "authentication" in msg.lower():
        return (
            f"{prefix} Your API key looks invalid — check it in the Settings tab. "
            "You can grab a new one at console.anthropic.com."
        )
    if "rate" in msg.lower() or "429" in msg:
        return f"{prefix} Anthropic rate-limited the request. Wait a minute and try again."
    if "timeout" in msg.lower():
        return f"{prefix} The request timed out. Check your internet and retry."
    if "invalid" in msg.lower() and "image" in msg.lower():
        return f"{prefix} Couldn't read that image — try a clearer photo (PNG or JPG)."
    return f"{prefix} {msg}"


# ---------------------------------------------------------------------------
# First-run wizard
# ---------------------------------------------------------------------------
def _wizard() -> None:
    """Three-step setup wizard for fresh installs."""
    st.title("Welcome to Runoff Reader")
    st.caption("by hark.equipment — tools for the trade")
    st.markdown(
        "Three quick steps and you're up. Under 60 seconds. You can change anything later "
        "in the **Configure** tab."
    )

    step = st.session_state.wizard_step
    progress_labels = ["Welcome", "Your garden", "API key", "Done"]
    cols = st.columns(len(progress_labels))
    for i, label in enumerate(progress_labels):
        with cols[i]:
            marker = "[*]" if i == step else ("[x]" if i < step else "[ ]")
            st.markdown(f"**{marker} {label}**")
    st.divider()

    if step == 0:
        st.subheader("Step 1 — what this thing does")
        st.markdown(
            "- Take a photo of your handwritten runoff log sheet.\n"
            "- Drop it in. Runoff Reader reads pH, EC, VWC, temp, humidity, CO2 — "
            "every value, every station, every room on the sheet.\n"
            "- Edit anything that didn't come out right.\n"
            "- Export clean CSV / JSON / Excel with flags on out-of-range readings.\n\n"
            "**You need:** an Anthropic API key (free to create — we'll grab it in step 3) "
            "and your log sheets. That's it."
        )
        if st.button("Start setup", type="primary"):
            st.session_state.wizard_step = 1
            st.rerun()

    elif step == 1:
        _wizard_garden_setup()

    elif step == 2:
        st.subheader("Step 3 — your Anthropic API key")
        st.markdown(
            "Get one at [console.anthropic.com/settings/keys]"
            "(https://console.anthropic.com/settings/keys). Free to make. "
            "Add a few dollars of credit — that covers months of normal use.\n\n"
            "Your key stays on this machine — saved to `~/.hark/credentials`. "
            "Nothing leaves your computer except the calls to Anthropic, "
            "which use your key directly."
        )
        key = st.text_input(
            "Anthropic API key", value=st.session_state.api_key, type="password",
            placeholder="sk-ant-...",
        )
        col_a, col_b, col_c = st.columns(3)
        if col_a.button("Back"):
            st.session_state.wizard_step = 1
            st.rerun()
        if col_b.button("Skip for now"):
            st.session_state.wizard_step = 3
            st.rerun()
        if col_c.button("Save and finish", type="primary"):
            if key.strip():
                credentials.save_api_key(key.strip())
                st.session_state.api_key = key.strip()
            st.session_state.wizard_step = 3
            st.rerun()

    elif step == 3:
        st.success("You're set. Drop in your first log sheet and hit EXTRACT.")
        if st.button("Enter Runoff Reader", type="primary"):
            st.session_state.wizard_complete = True
            st.rerun()


def _wizard_garden_setup() -> None:
    """Step 2 — Garden details: zones, rooms, units, Solus toggle."""
    st.subheader("Step 2 — your garden")
    st.markdown(
        "Tell us how your garden is laid out so we can read your sheets correctly. "
        "Don't overthink it — every value below is editable later."
    )

    # Load current config (example by default) for sensible starting values.
    try:
        existing = config_loader.load_config()
    except Exception:
        existing = {"facility": {"name": "My Garden", "buildings": [], "units": {"temperature": "F", "co2": "ppm"}, "solus_ec_enabled": False}}
    facility = existing.get("facility", {})

    garden_name = st.text_input(
        "What do you call your garden?",
        value=facility.get("name", "My Garden"),
        help="Just for your own reference — never sent anywhere.",
        placeholder="e.g. North Greenhouse, Garage Tent, Veg Room",
    )

    temp_unit = st.radio(
        "Temperature unit",
        options=["F", "C"],
        index=0 if facility.get("units", {}).get("temperature", "F") == "F" else 1,
        horizontal=True,
    )

    st.divider()
    st.markdown("**Zones in your garden**")
    st.caption(
        "A zone is a building, room, tent, or section that you track separately on its own log sheet. "
        "Most growers have 1–3 zones. Each zone can hold multiple rooms (e.g. 'Greenhouse A' might "
        "have rooms 1 through 4)."
    )

    if "wizard_zones" not in st.session_state:
        existing_buildings = facility.get("buildings") or [
            {"code": "A", "label": "Zone A", "rooms": [1, 2, 3, 4], "room_label_template": "Room {n}"}
        ]
        st.session_state.wizard_zones = [
            {
                "code": b.get("code", "A"),
                "label": b.get("label", f"Zone {b.get('code', 'A')}"),
                "rooms_count": len(b.get("rooms") or [1, 2, 3, 4]),
                "room_label_template": b.get("room_label_template", "Room {n}"),
            }
            for b in existing_buildings
        ]

    new_zones: List[Dict[str, Any]] = []
    for i, z in enumerate(st.session_state.wizard_zones):
        with st.container(border=True):
            st.markdown(f"**Zone {i + 1}**")
            col_a, col_b = st.columns([2, 1])
            label = col_a.text_input(
                "What do you call this zone?",
                value=z.get("label", f"Zone {i + 1}"),
                key=f"wz_label_{i}",
                placeholder="e.g. Greenhouse A, North Tent, Veg Room",
            )
            code = col_b.text_input(
                "Short code",
                value=z.get("code", chr(65 + i)),
                key=f"wz_code_{i}",
                help="What's written at the top-left of your log sheets to identify a room in this zone. Keep it short (1–3 letters).",
                placeholder="A",
            ).strip().upper()
            rooms_count = st.number_input(
                "How many rooms/tents in this zone?",
                min_value=1,
                max_value=50,
                value=int(z.get("rooms_count", 4)),
                step=1,
                key=f"wz_rooms_{i}",
            )
            template = st.text_input(
                "How are rooms labeled? (use {n} for the number)",
                value=z.get("room_label_template", "Room {n}"),
                key=f"wz_tpl_{i}",
                help="e.g. 'Room {n}' becomes Room 1, Room 2, etc. Use 'Flower {n}' if your sheets say 'Flower 3'.",
            )
            remove = st.checkbox("Remove this zone", key=f"wz_rm_{i}")
            if not remove and code:
                new_zones.append(
                    {
                        "code": code,
                        "label": label or f"Zone {i + 1}",
                        "rooms_count": int(rooms_count),
                        "room_label_template": template or "Room {n}",
                    }
                )

    if st.button("+ Add another zone"):
        next_letter = chr(65 + len(st.session_state.wizard_zones))
        st.session_state.wizard_zones.append(
            {
                "code": next_letter,
                "label": f"Zone {next_letter}",
                "rooms_count": 4,
                "room_label_template": "Room {n}",
            }
        )
        st.rerun()

    st.session_state.wizard_zones = new_zones

    st.divider()
    with st.expander("Advanced — sensor and thresholds"):
        solus = st.checkbox(
            "I log a separate Solus EC reading per station (X.XX format)",
            value=bool(facility.get("solus_ec_enabled", False)),
            help=(
                "Most growers leave this off. Only check it if your sheets log TWO EC values per "
                "station — a regular one-decimal EC and a two-decimal Solus EC from a dedicated sensor."
            ),
        )
        st.caption(
            "pH and EC threshold values are kept at industry-standard defaults (pH 5.6–6.3, EC 1.5–5.5). "
            "Adjust later in the Configure tab if your SOP differs."
        )

    st.divider()
    col_back, col_save = st.columns(2)
    if col_back.button("Back"):
        st.session_state.wizard_step = 0
        st.rerun()
    if col_save.button("Save garden and continue", type="primary"):
        thresholds = facility.get("thresholds") or {
            "ph": {"high": 6.3, "low": 5.6, "borderline_high": 6.1, "borderline_low": 5.8},
            "ec": {"high": 5.5, "low": 1.5, "borderline_high": 3.5, "borderline_low": 2.8},
            "combo_flag": {"ph_high": 6.1, "ec_high": 3.5, "ph_low": 5.6, "ec_low": 2.8},
        }
        new_cfg = {
            "facility": {
                "name": garden_name or "My Garden",
                "units": {"temperature": temp_unit, "co2": "ppm"},
                "solus_ec_enabled": bool(solus),
                "buildings": [
                    {
                        "code": z["code"],
                        "label": z["label"],
                        "rooms": list(range(1, int(z["rooms_count"]) + 1)),
                        "room_label_template": z["room_label_template"],
                    }
                    for z in new_zones
                ],
                "log_sources": ["handwritten_runoff"],
                "exclude_keywords": ["veg", "vegetation", "clone", "clones", "mother", "mom"],
                "thresholds": thresholds,
            }
        }
        if not new_zones:
            st.error("Add at least one zone before continuing — every garden needs at least one zone to track.")
        else:
            config_loader.save_config(new_cfg)
            st.session_state.pop("wizard_zones", None)
            st.session_state.wizard_step = 2
            st.rerun()


# ---------------------------------------------------------------------------
# Tab: Extract
# ---------------------------------------------------------------------------
def _tab_extract(cfg: Dict[str, Any]) -> None:
    st.header("Extract")

    st.info(
        "**v1 — early access.** Built for *accuracy via your edits*, not 100% OCR. "
        "Every value below is editable. Add rooms with the **+** at the bottom of the table. "
        "Right-click a row to delete it. v2 with the polished tile-based phone UI ships in 2–4 weeks "
        "— free for all v1 buyers, forever."
    )

    buildings = _building_codes(cfg)
    if not buildings:
        st.warning("No buildings configured yet. Visit the Configure tab.")
        return

    uploaded = st.file_uploader(
        "Drop images here (PNG / JPG, multi-select OK)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

    col1, col2 = st.columns([1, 1])
    if col1.button("Try with sample image", help="Loads a built-in sample log for smoke testing"):
        if SAMPLE_IMAGE.exists():
            st.session_state["_use_sample"] = True
            st.rerun()
        else:
            st.warning(
                "No sample image found. Drop one at assets/sample_log.png "
                "or copy a screenshot from your phone first."
            )
    if col2.button("Clear uploads"):
        st.session_state["_use_sample"] = False
        st.session_state.last_result = None
        st.rerun()

    image_payloads: List[ImagePayload] = []

    if uploaded:
        for f in uploaded:
            try:
                payload = extraction.compress_image(
                    f.read(),
                    max_width=st.session_state.max_width,
                    jpeg_quality=st.session_state.jpeg_quality,
                )
                payload.name = f.name
                image_payloads.append(payload)
            except Exception as e:
                st.error(_friendly_error(f"Couldn't read {f.name}.", e))

    if st.session_state.get("_use_sample") and SAMPLE_IMAGE.exists():
        try:
            payload = extraction.compress_image(
                SAMPLE_IMAGE.read_bytes(),
                max_width=st.session_state.max_width,
                jpeg_quality=st.session_state.jpeg_quality,
            )
            payload.name = SAMPLE_IMAGE.name
            image_payloads.append(payload)
        except Exception as e:
            st.error(_friendly_error("Sample image failed.", e))

    if image_payloads:
        st.caption(f"{len(image_payloads)} image(s) staged")
        thumbs = st.columns(min(4, len(image_payloads)))
        for i, img in enumerate(image_payloads):
            with thumbs[i % len(thumbs)]:
                try:
                    raw = img.base64
                    import base64 as _b64
                    Image.open(io.BytesIO(_b64.b64decode(raw)))
                    st.image(
                        _b64.b64decode(raw),
                        caption=img.name,
                        use_column_width=True,
                    )
                except Exception:
                    st.caption(img.name)

    st.divider()
    room_override = st.text_input(
        "Room ID override (optional — only for single-room images where the room code isn't visible)",
        placeholder="e.g. AB1 — leave blank if room IDs are written on the sheets",
    )

    has_result = st.session_state.last_result is not None
    btn_label = "RE-EXTRACT" if has_result else "EXTRACT"
    if st.button(btn_label, type="primary", disabled=not image_payloads):
        if not st.session_state.api_key:
            st.error(
                "No API key set. Go to the Settings tab and paste your Anthropic key."
            )
            return
        with st.spinner("Calling Claude — usually 5 to 20 seconds…"):
            try:
                result = extraction.extract(
                    image_payloads=image_payloads,
                    config=cfg,
                    api_key=st.session_state.api_key,
                    model=st.session_state.model,
                    building=None,
                    room_override=room_override or None,
                )
                st.session_state.last_result = result
                st.session_state.pop("results_editor", None)
                st.session_state.pop("_edited_rows_cache", None)
                history.save_extraction(result)
            except Exception as e:
                st.error(_friendly_error("Extraction failed.", e))
                return

    result = st.session_state.last_result
    if result is not None:
        st.subheader("Draft — edit fields as needed")
        st.caption(
            "? = ambiguous read · empty cells = missing data · "
            "Click the + at the bottom of the table to add a room manually · "
            "Right-click a row to delete · S4/S5 columns are optional, leave blank if your facility uses 3 stations."
        )

        df = _rows_to_editor_df(result.rows)

        edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config=_editor_column_config(cfg),
            key="results_editor",
        )

        with st.expander("Raw model output (read-only — what Claude returned)"):
            st.text_area(
                "Raw text",
                result.raw_text,
                height=200,
                label_visibility="collapsed",
            )

        _download_buttons(edited, result, cfg)
        _trellis_export_section(edited, result)


def _trellis_export_section(
    edited_df: pd.DataFrame,
    original: extraction.ExtractionResult,
) -> None:
    """Render the 'Push to Trellis' button. Disabled if no URL configured."""
    st.divider()
    st.markdown("**Push to Trellis**")
    st.caption(
        "Send these readings to your Trellis dashboard. "
        "Set the Trellis URL in the Settings tab."
    )
    trellis_url = (st.session_state.get("trellis_url") or "").strip()
    rows = _df_to_rows(edited_df)
    has_rows = len(rows) > 0
    disabled = (not trellis_url) or (not has_rows)
    tooltip = None
    if not trellis_url:
        tooltip = "Add a Trellis URL in the Settings tab first."
    elif not has_rows:
        tooltip = "Nothing to push — add at least one room row."
    if st.button(
        "Push to Trellis",
        type="primary",
        disabled=disabled,
        help=tooltip,
        key="push_to_trellis_btn",
    ):
        with st.spinner("Pushing to Trellis…"):
            try:
                result = export_to_trellis(
                    [r.to_dict() for r in rows],
                    trellis_url=trellis_url,
                    auto_create_rooms=True,
                )
            except Exception as e:  # belt-and-suspenders; module catches its own
                st.error(_friendly_error("Push failed.", e))
                return
        if result.get("ok"):
            resp = result.get("response") or {}
            inserted = resp.get("insertedCount", 0)
            rooms_created = resp.get("roomsCreated", 0)
            flagged = resp.get("flaggedCount", 0)
            st.success(
                f"Pushed {inserted} reading(s) to Trellis. "
                f"{rooms_created} new room(s). {flagged} flagged."
            )
            warnings = resp.get("warnings") or []
            for w in warnings:
                st.warning(w)
            skipped = result.get("skipped") or []
            if skipped:
                st.caption(f"{len(skipped)} row(s) skipped locally (missing data).")
        else:
            st.error(result.get("error") or "Push failed.")


def _rows_to_editor_df(rows: List[extraction.RoomReading]) -> pd.DataFrame:
    """Build a DataFrame in the editor's column order from RoomReading rows."""
    if not rows:
        return pd.DataFrame(columns=exporters.CSV_COLUMNS)
    records = []
    for r in rows:
        d = r.to_dict()
        d["flags"] = ";".join(d.get("flags") or [])
        records.append(d)
    df = pd.DataFrame(records)
    for col in exporters.CSV_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[exporters.CSV_COLUMNS]


def _editor_column_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Per-column input config for the editable results table."""
    temp_unit = cfg.get("facility", {}).get("units", {}).get("temperature", "F")
    co2_unit = cfg.get("facility", {}).get("units", {}).get("co2", "ppm")

    ph_col = lambda label: st.column_config.NumberColumn(
        label, min_value=0.0, max_value=14.0, step=0.1, format="%.1f"
    )
    ec_col = lambda label: st.column_config.NumberColumn(
        label, min_value=0.0, max_value=20.0, step=0.1, format="%.1f"
    )
    vwc_col = lambda label: st.column_config.NumberColumn(
        label, min_value=0.0, max_value=100.0, step=1.0, format="%d"
    )
    sec_col = lambda label: st.column_config.NumberColumn(
        label, min_value=0.0, max_value=20.0, step=0.01, format="%.2f"
    )

    return {
        "room": st.column_config.TextColumn("Room", required=True, width="small"),
        "day": st.column_config.NumberColumn(
            "Day", min_value=0, max_value=365, step=1, width="small"
        ),
        "IN_pH": ph_col("IN pH"),
        "IN_EC": ec_col("IN EC"),
        "IN_VWC": vwc_col("IN VWC%"),
        "IN_solus": sec_col("IN Solus"),
        "S1_pH": ph_col("S1 pH"),
        "S1_EC": ec_col("S1 EC"),
        "S1_VWC": vwc_col("S1 VWC%"),
        "S1_solus": sec_col("S1 Solus"),
        "S2_pH": ph_col("S2 pH"),
        "S2_EC": ec_col("S2 EC"),
        "S2_VWC": vwc_col("S2 VWC%"),
        "S2_solus": sec_col("S2 Solus"),
        "S3_pH": ph_col("S3 pH"),
        "S3_EC": ec_col("S3 EC"),
        "S3_VWC": vwc_col("S3 VWC%"),
        "S3_solus": sec_col("S3 Solus"),
        "S4_pH": ph_col("S4 pH"),
        "S4_EC": ec_col("S4 EC"),
        "S4_VWC": vwc_col("S4 VWC%"),
        "S4_solus": sec_col("S4 Solus"),
        "S5_pH": ph_col("S5 pH"),
        "S5_EC": ec_col("S5 EC"),
        "S5_VWC": vwc_col("S5 VWC%"),
        "S5_solus": sec_col("S5 Solus"),
        "temp": st.column_config.NumberColumn(f"Temp °{temp_unit}", step=1, format="%d"),
        "humidity": st.column_config.NumberColumn("Hum %", step=1, format="%d"),
        "co2": st.column_config.NumberColumn(f"CO2 {co2_unit}", step=10, format="%d"),
        "notes": st.column_config.TextColumn("Notes"),
        "flags": st.column_config.TextColumn("Flags"),
    }


def _df_to_rows(df: pd.DataFrame) -> List[extraction.RoomReading]:
    """Convert the edited DataFrame back to RoomReading objects."""
    rows: List[extraction.RoomReading] = []
    valid_fields = {f for f in extraction.RoomReading.__dataclass_fields__}
    for _, row in df.iterrows():
        room_raw = row.get("room")
        room = str(room_raw).strip().upper() if room_raw is not None and not pd.isna(room_raw) else ""
        if not room:
            continue

        kwargs: Dict[str, Any] = {"room": room}
        for col in exporters.CSV_COLUMNS:
            if col in ("room", "flags"):
                continue
            if col not in valid_fields:
                continue
            if col not in row.index:
                continue
            val = row[col]
            if val is None or (isinstance(val, float) and pd.isna(val)) or pd.isna(val):
                continue
            kwargs[col] = val

        if "day" in kwargs:
            try:
                kwargs["day"] = int(kwargs["day"])
            except (ValueError, TypeError):
                kwargs.pop("day", None)
        if "co2" in kwargs:
            try:
                kwargs["co2"] = int(kwargs["co2"])
            except (ValueError, TypeError):
                kwargs.pop("co2", None)
        if "notes" in kwargs and not isinstance(kwargs["notes"], str):
            kwargs["notes"] = str(kwargs["notes"])

        flags_raw = row.get("flags")
        if isinstance(flags_raw, str) and flags_raw.strip():
            kwargs["flags"] = [f.strip() for f in flags_raw.split(";") if f.strip()]

        rows.append(extraction.RoomReading(**kwargs))
    return rows


def _download_buttons(
    edited_df: pd.DataFrame,
    original: extraction.ExtractionResult,
    cfg: Dict[str, Any],
) -> None:
    """Build exports from the EDITED DataFrame, not the original rows."""
    new_rows = _df_to_rows(edited_df)
    new_result = extraction.ExtractionResult(
        raw_text=original.raw_text,
        rows=new_rows,
        model=original.model,
        source_images=original.source_images,
        building=original.building,
        room_override=original.room_override,
    )
    thresholds = cfg["facility"]["thresholds"]

    st.caption(f"{len(new_rows)} room(s) will be exported.")
    col_csv, col_json, col_xlsx = st.columns(3)
    col_csv.download_button(
        "Download CSV",
        data=exporters.to_csv(new_result),
        file_name="runoff_reader_extraction.csv",
        mime="text/csv",
        use_container_width=True,
    )
    col_json.download_button(
        "Download JSON",
        data=exporters.to_json(new_result),
        file_name="runoff_reader_extraction.json",
        mime="application/json",
        use_container_width=True,
    )
    col_xlsx.download_button(
        "Download XLSX (with flag highlighting)",
        data=exporters.to_xlsx(new_result, thresholds),
        file_name="runoff_reader_extraction.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Tab: Configure
# ---------------------------------------------------------------------------
def _tab_configure(cfg: Dict[str, Any]) -> None:
    st.header("Configure your garden")
    st.caption(
        "Edits here save to `config/facility.yaml`. The shipped example is never "
        "overwritten — use 'Reset to example' to start over."
    )

    facility = cfg.get("facility", {})
    name = st.text_input("Garden name", value=facility.get("name", "My Garden"))

    st.subheader("Units")
    units = facility.get("units", {"temperature": "F", "co2": "ppm"})
    col_a, col_b = st.columns(2)
    units["temperature"] = col_a.selectbox(
        "Temperature unit",
        options=["F", "C"],
        index=0 if units.get("temperature", "F") == "F" else 1,
    )
    units["co2"] = col_b.selectbox(
        "CO2 unit", options=["ppm"], index=0
    )

    st.subheader("Zones in your garden")
    st.caption(
        "A zone is a section, building, tent, or room block you track on its own log sheet. "
        "Rooms is a comma-separated list of numbers. Template uses `{n}` for the room number."
    )
    buildings = facility.get("buildings", [])
    edited_buildings: List[Dict[str, Any]] = []
    for i, b in enumerate(list(buildings)):
        with st.expander(f"Zone: {b.get('label') or b.get('code', '?')}", expanded=False):
            code = st.text_input(
                f"Short code (1-3 letters, written on your log sheets)",
                value=b.get("code", ""), key=f"bc_{i}",
            )
            label = st.text_input(
                f"What you call this zone",
                value=b.get("label", f"Zone {code}"), key=f"bl_{i}",
            )
            rooms_text = st.text_input(
                f"Room numbers in this zone (comma-separated)",
                value=",".join(str(r) for r in b.get("rooms", [])),
                key=f"br_{i}",
            )
            template = st.text_input(
                f"How rooms are labeled (use {{n}} for the number)",
                value=b.get("room_label_template", "Room {n}"),
                key=f"bt_{i}",
            )
            remove = st.checkbox(f"Remove this zone", key=f"rm_{i}")
            if not remove and code:
                try:
                    rooms = [int(x.strip()) for x in rooms_text.split(",") if x.strip()]
                except ValueError:
                    rooms = []
                edited_buildings.append(
                    {
                        "code": code.upper(),
                        "label": label,
                        "rooms": rooms,
                        "room_label_template": template,
                    }
                )

    if st.button("+ Add another zone"):
        edited_buildings.append(
            {
                "code": "NEW",
                "label": "New Zone",
                "rooms": [1, 2, 3, 4],
                "room_label_template": "Room {n}",
            }
        )

    st.subheader("Thresholds")
    thresholds = facility.get("thresholds", {})
    ph_t = thresholds.get("ph", {})
    ec_t = thresholds.get("ec", {})
    combo = thresholds.get("combo_flag", {})

    st.markdown("**pH**")
    col_a, col_b, col_c, col_d = st.columns(4)
    ph_t["high"] = col_a.number_input("pH high", value=float(ph_t.get("high", 6.3)), step=0.1)
    ph_t["low"] = col_b.number_input("pH low", value=float(ph_t.get("low", 5.6)), step=0.1)
    ph_t["borderline_high"] = col_c.number_input(
        "pH borderline high", value=float(ph_t.get("borderline_high", 6.1)), step=0.1
    )
    ph_t["borderline_low"] = col_d.number_input(
        "pH borderline low", value=float(ph_t.get("borderline_low", 5.8)), step=0.1
    )

    st.markdown("**EC**")
    col_a, col_b, col_c, col_d = st.columns(4)
    ec_t["high"] = col_a.number_input("EC high", value=float(ec_t.get("high", 5.5)), step=0.1)
    ec_t["low"] = col_b.number_input("EC low", value=float(ec_t.get("low", 1.5)), step=0.1)
    ec_t["borderline_high"] = col_c.number_input(
        "EC borderline high", value=float(ec_t.get("borderline_high", 3.5)), step=0.1
    )
    ec_t["borderline_low"] = col_d.number_input(
        "EC borderline low", value=float(ec_t.get("borderline_low", 2.8)), step=0.1
    )

    st.markdown("**Combo flag (both fire together)**")
    col_a, col_b, col_c, col_d = st.columns(4)
    combo["ph_high"] = col_a.number_input(
        "pH high combo", value=float(combo.get("ph_high", 6.1)), step=0.1
    )
    combo["ec_high"] = col_b.number_input(
        "EC high combo", value=float(combo.get("ec_high", 3.5)), step=0.1
    )
    combo["ph_low"] = col_c.number_input(
        "pH low combo", value=float(combo.get("ph_low", 5.6)), step=0.1
    )
    combo["ec_low"] = col_d.number_input(
        "EC low combo", value=float(combo.get("ec_low", 2.8)), step=0.1
    )

    st.subheader("Solus EC")
    solus_enabled = st.checkbox(
        "I log a separate Solus EC reading per station (X.XX format)",
        value=bool(facility.get("solus_ec_enabled", False)),
        help=(
            "Most growers leave this OFF. Only check it if your log sheets record TWO EC values "
            "per station — a regular one-decimal EC plus a two-decimal Solus EC."
        ),
    )

    st.divider()
    col_save, col_reset = st.columns(2)
    if col_save.button("Save config", type="primary"):
        new_cfg = {
            "facility": {
                "name": name,
                "buildings": edited_buildings,
                "units": units,
                "solus_ec_enabled": bool(solus_enabled),
                "log_sources": facility.get(
                    "log_sources", ["handwritten_runoff"],
                ),
                "exclude_keywords": facility.get(
                    "exclude_keywords",
                    ["veg", "vegetation", "clone", "clones", "mother", "mom"],
                ),
                "thresholds": {
                    "ph": ph_t,
                    "ec": ec_t,
                    "combo_flag": combo,
                },
            }
        }
        config_loader.save_config(new_cfg)
        st.success("Saved. Switch to the Extract tab to use the new config.")

    if col_reset.button("Reset to example"):
        config_loader.reset_to_example()
        st.success("Restored the shipped example. Refresh to see it.")


# ---------------------------------------------------------------------------
# Tab: History
# ---------------------------------------------------------------------------
def _tab_history(cfg: Dict[str, Any]) -> None:
    st.header("Extraction history")
    st.caption("Local SQLite. Nothing leaves your machine.")

    rows = history.list_recent(limit=50)
    if not rows:
        st.info("No extractions yet. Run one from the Extract tab.")
        return

    for h in rows:
        with st.expander(
            f"#{h['id']} - {h['created_at']} - {h['building'] or '(no building)'} - {h['row_count']} rows"
        ):
            st.write(
                f"**Model:** {h['model']}  \n"
                f"**Room override:** {h['room_override'] or '(none)'}  \n"
                f"**Images:** {', '.join(h['source_images']) or '(none)'}"
            )
            col_a, col_b, col_c = st.columns(3)
            if col_a.button("Re-load", key=f"reload_{h['id']}"):
                result = history.get_extraction(h["id"])
                if result:
                    st.session_state.last_result = result
                    st.success("Loaded into the Extract tab.")
            if col_b.button("Delete", key=f"del_{h['id']}"):
                history.delete_extraction(h["id"])
                st.rerun()
            result = history.get_extraction(h["id"])
            if result:
                with col_c:
                    st.download_button(
                        "CSV",
                        data=exporters.to_csv(result),
                        file_name=f"extraction_{h['id']}.csv",
                        mime="text/csv",
                        key=f"csv_{h['id']}",
                    )

    st.divider()
    if st.button("Clear all history", type="secondary"):
        history.clear_history()
        st.rerun()


# ---------------------------------------------------------------------------
# Tab: Settings
# ---------------------------------------------------------------------------
def _tab_settings() -> None:
    st.header("Settings")
    st.caption("API key + model + image compression. All local.")

    st.subheader("Trellis URL")
    st.markdown(
        "Base URL of your Trellis dashboard. Leave blank if you don't use Trellis. "
        "For local dev, use `http://localhost:5050`."
    )
    trellis_url_input = st.text_input(
        "Trellis URL",
        value=st.session_state.get("trellis_url", ""),
        placeholder="https://trellis.example.com",
        key="trellis_url_input",
    )
    col_t_save, col_t_clear = st.columns(2)
    if col_t_save.button("Save Trellis URL"):
        val = (trellis_url_input or "").strip().rstrip("/")
        if not val:
            st.session_state.trellis_url = ""
            st.success("Trellis URL cleared.")
        elif not (val.startswith("http://") or val.startswith("https://")):
            st.error("Trellis URL must start with http:// or https://.")
        else:
            st.session_state.trellis_url = val
            st.success("Trellis URL saved for this session.")
    if col_t_clear.button("Forget Trellis URL"):
        st.session_state.trellis_url = ""
        st.success("Cleared.")

    st.divider()
    st.subheader("Anthropic API key")
    st.markdown(
        "Saved to `~/.hark/credentials` with 600 perms. "
        "Get a key at [console.anthropic.com](https://console.anthropic.com/settings/keys)."
    )
    key = st.text_input(
        "API key",
        value=st.session_state.api_key,
        type="password",
        placeholder="sk-ant-...",
    )
    col_a, col_b = st.columns(2)
    if col_a.button("Save key", type="primary"):
        if key.strip():
            credentials.save_api_key(key.strip())
            st.session_state.api_key = key.strip()
            st.success("Saved.")
        else:
            st.warning("Empty key — nothing saved.")
    if col_b.button("Forget key"):
        credentials.clear_api_key()
        st.session_state.api_key = ""
        st.success("Removed from disk.")

    st.divider()
    st.subheader("Model")
    st.session_state.model = st.text_input(
        "Anthropic model ID",
        value=st.session_state.model,
        help="Default: claude-sonnet-4-6. Change at your own risk.",
    )

    st.subheader("Image compression (saves Anthropic tokens)")
    st.session_state.max_width = st.slider(
        "Max image width (px)", min_value=400, max_value=2000,
        value=int(st.session_state.max_width), step=50,
    )
    st.session_state.jpeg_quality = st.slider(
        "JPEG quality", min_value=40, max_value=95,
        value=int(st.session_state.jpeg_quality), step=1,
    )
    st.caption(
        "Lower values = cheaper extractions but blurrier images. "
        "Defaults are tuned for TrolMaster screens."
    )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def main() -> None:
    if not st.session_state.wizard_complete:
        _wizard()
        return

    cfg = _load_cfg()
    if not cfg:
        _wizard()
        return

    st.caption(
        f"Garden: **{cfg['facility'].get('name', 'My Garden')}** - "
        "all data stays on this machine."
    )

    tab_extract, tab_configure, tab_history, tab_settings = st.tabs(
        ["Extract", "Configure", "History", "Settings"]
    )
    with tab_extract:
        _tab_extract(cfg)
    with tab_configure:
        _tab_configure(cfg)
    with tab_history:
        _tab_history(cfg)
    with tab_settings:
        _tab_settings()


if __name__ == "__main__":
    main()
