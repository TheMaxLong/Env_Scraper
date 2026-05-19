"""SQLite-backed extraction history.

Stores: timestamp, building, room override, source image names, raw text,
structured rows (JSON). Local only. No telemetry.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.extraction import ExtractionResult, RoomReading

APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / "history.db"


def _conn() -> sqlite3.Connection:
    """Return a sqlite connection, creating the schema if missing."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS extractions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL,
            building    TEXT,
            room_override TEXT,
            model       TEXT,
            source_images TEXT,
            row_count   INTEGER,
            raw_text    TEXT,
            rows_json   TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_extraction(result: ExtractionResult) -> int:
    """Persist one extraction. Returns the new row id."""
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO extractions
              (created_at, building, room_override, model, source_images,
               row_count, raw_text, rows_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat() + "Z",
                result.building,
                result.room_override,
                result.model,
                json.dumps(result.source_images),
                len(result.rows),
                result.raw_text,
                json.dumps([r.to_dict() for r in result.rows], default=str),
            ),
        )
        return cur.lastrowid or 0


def list_recent(limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent N extractions as plain dicts."""
    with _conn() as conn:
        cur = conn.execute(
            """
            SELECT id, created_at, building, room_override, model,
                   source_images, row_count
              FROM extractions
             ORDER BY id DESC
             LIMIT ?
            """,
            (limit,),
        )
        out = []
        for row in cur.fetchall():
            d = dict(row)
            try:
                d["source_images"] = json.loads(d.get("source_images") or "[]")
            except json.JSONDecodeError:
                d["source_images"] = []
            out.append(d)
        return out


def get_extraction(extraction_id: int) -> Optional[ExtractionResult]:
    """Load one full extraction back into an ExtractionResult."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM extractions WHERE id = ?", (extraction_id,)
        ).fetchone()
    if not row:
        return None

    try:
        source_images = json.loads(row["source_images"] or "[]")
    except json.JSONDecodeError:
        source_images = []
    try:
        rows_data = json.loads(row["rows_json"] or "[]")
    except json.JSONDecodeError:
        rows_data = []

    rebuilt: List[RoomReading] = []
    for rd in rows_data:
        try:
            rebuilt.append(RoomReading(**rd))
        except TypeError:
            # Tolerate older schemas: copy known fields only.
            allowed = {k: rd[k] for k in rd if k in RoomReading.__annotations__}
            rebuilt.append(RoomReading(**allowed))

    return ExtractionResult(
        raw_text=row["raw_text"] or "",
        rows=rebuilt,
        model=row["model"] or "",
        source_images=source_images,
        building=row["building"],
        room_override=row["room_override"],
    )


def delete_extraction(extraction_id: int) -> None:
    """Remove one history entry."""
    with _conn() as conn:
        conn.execute("DELETE FROM extractions WHERE id = ?", (extraction_id,))
        conn.commit()


def clear_history() -> None:
    """Wipe all history (the buyer's choice)."""
    with _conn() as conn:
        conn.execute("DELETE FROM extractions")
        conn.commit()
