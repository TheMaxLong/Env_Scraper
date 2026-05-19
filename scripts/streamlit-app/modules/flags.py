"""Threshold-based flag logic for pH and EC readings.

Mirrors the Flower-Room-Display rules from the original tool:
  - pH >= high                       -> HIGH
  - pH <= low                        -> LOW
  - pH >= combo.ph_high AND EC >= combo.ec_high -> COMBO_HIGH (flag both)
  - pH <= combo.ph_low  AND EC <= combo.ec_low  -> COMBO_LOW  (flag both)

Borderline values get a softer flag for the spreadsheet conditional formatting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Flag:
    """A single threshold trigger for a reading."""
    severity: str   # "high", "low", "borderline", "combo"
    field: str      # "ph" or "ec"
    reason: str     # Human-readable explanation


def _to_float(value: Any) -> Optional[float]:
    """Best-effort numeric coercion. Returns None if not a number."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_reading(
    ph: Any,
    ec: Any,
    thresholds: Dict[str, Any],
) -> List[Flag]:
    """Return the list of flags that apply to one pH/EC pair.

    Args:
        ph: pH reading (any type, coerced).
        ec: EC reading (any type, coerced).
        thresholds: The 'thresholds' block from the facility config.

    Returns:
        A list of Flag objects. Empty list means the reading is in range.
    """
    flags: List[Flag] = []
    ph_v = _to_float(ph)
    ec_v = _to_float(ec)

    ph_t = thresholds.get("ph", {})
    ec_t = thresholds.get("ec", {})
    combo = thresholds.get("combo_flag", {})

    if ph_v is not None:
        if ph_v >= ph_t.get("high", 6.3):
            flags.append(Flag("high", "ph", f"pH {ph_v} >= {ph_t.get('high')}"))
        elif ph_v <= ph_t.get("low", 5.6):
            flags.append(Flag("low", "ph", f"pH {ph_v} <= {ph_t.get('low')}"))
        elif ph_v >= ph_t.get("borderline_high", 6.1):
            flags.append(Flag("borderline", "ph", f"pH {ph_v} borderline high"))
        elif ph_v <= ph_t.get("borderline_low", 5.8):
            flags.append(Flag("borderline", "ph", f"pH {ph_v} borderline low"))

    if ec_v is not None:
        if ec_v >= ec_t.get("high", 5.5):
            flags.append(Flag("high", "ec", f"EC {ec_v} >= {ec_t.get('high')}"))
        elif ec_v <= ec_t.get("low", 1.5):
            flags.append(Flag("low", "ec", f"EC {ec_v} <= {ec_t.get('low')}"))

    # Combo flags: both pH and EC together
    if ph_v is not None and ec_v is not None:
        if ph_v >= combo.get("ph_high", 6.1) and ec_v >= combo.get("ec_high", 3.5):
            flags.append(Flag("combo", "ph", "pH high + EC high combo"))
            flags.append(Flag("combo", "ec", "pH high + EC high combo"))
        if ph_v <= combo.get("ph_low", 5.6) and ec_v <= combo.get("ec_low", 2.8):
            flags.append(Flag("combo", "ph", "pH low + EC low combo"))
            flags.append(Flag("combo", "ec", "pH low + EC low combo"))

    return flags


def flag_row(row: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, List[Flag]]:
    """Return a dict mapping pH/EC field names to their flags.

    Expects keys like IN_pH, IN_EC, S1_pH, S1_EC, etc. Covers IN + S1..S5.
    """
    pairs = [
        ("IN_pH", "IN_EC"),
        ("S1_pH", "S1_EC"),
        ("S2_pH", "S2_EC"),
        ("S3_pH", "S3_EC"),
        ("S4_pH", "S4_EC"),
        ("S5_pH", "S5_EC"),
    ]
    result: Dict[str, List[Flag]] = {}
    for ph_key, ec_key in pairs:
        flags = evaluate_reading(row.get(ph_key), row.get(ec_key), thresholds)
        result[ph_key] = [f for f in flags if f.field == "ph"]
        result[ec_key] = [f for f in flags if f.field == "ec"]
    return result


def severity_of(flag_list: List[Flag]) -> Optional[str]:
    """Return the most serious severity for a list of flags."""
    if not flag_list:
        return None
    order = {"combo": 0, "high": 1, "low": 1, "borderline": 2}
    return sorted(flag_list, key=lambda f: order.get(f.severity, 99))[0].severity
