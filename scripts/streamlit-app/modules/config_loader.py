"""Load and save the facility YAML config.

The example config ships with the app. User edits land in facility.yaml,
which is gitignored so buyer-specific settings never leak.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

import yaml

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_ROOT / "config"
EXAMPLE_PATH = CONFIG_DIR / "facility.example.yaml"
USER_PATH = CONFIG_DIR / "facility.yaml"


def config_exists() -> bool:
    """Return True if the user has saved their own facility config."""
    return USER_PATH.exists()


def load_config() -> Dict[str, Any]:
    """Load the active config. Falls back to the example if user has none."""
    path = USER_PATH if USER_PATH.exists() else EXAMPLE_PATH
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not data or "facility" not in data:
        raise ValueError(
            "Facility config is missing the top-level 'facility:' key. "
            "Open the Configure tab and click 'Reset to example' to fix."
        )
    return data


def save_config(data: Dict[str, Any]) -> Path:
    """Write the given config dict to the user config path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with USER_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, default_flow_style=False)
    return USER_PATH


def reset_to_example() -> Path:
    """Copy the shipped example over the user config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_PATH, USER_PATH)
    return USER_PATH


def list_buildings(cfg: Dict[str, Any]) -> list[str]:
    """Return the building codes (e.g. ['AB', 'EF', 'GH'])."""
    return [b["code"] for b in cfg["facility"].get("buildings", [])]


def get_building(cfg: Dict[str, Any], code: str) -> Dict[str, Any] | None:
    """Look up one building block by its code."""
    for b in cfg["facility"].get("buildings", []):
        if b["code"].upper() == code.upper():
            return b
    return None
