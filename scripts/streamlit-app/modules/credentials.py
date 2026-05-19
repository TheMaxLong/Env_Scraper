"""Anthropic API key storage at ~/.hark/credentials.

Outside the repo so the key never gets committed by accident.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

CRED_DIR = Path.home() / ".hark"
CRED_PATH = CRED_DIR / "credentials"


def load_api_key() -> Optional[str]:
    """Return the saved key, falling back to the ANTHROPIC_API_KEY env var."""
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key.strip()
    if not CRED_PATH.exists():
        return None
    try:
        text = CRED_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            if key.strip().upper() == "ANTHROPIC_API_KEY":
                return val.strip().strip('"').strip("'")
        else:
            return line   # Plain key on a line by itself.
    return None


def save_api_key(key: str) -> Path:
    """Write the key to ~/.hark/credentials with restrictive permissions."""
    CRED_DIR.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(f"ANTHROPIC_API_KEY={key.strip()}\n", encoding="utf-8")
    try:
        os.chmod(CRED_PATH, 0o600)
    except OSError:
        # On filesystems that don't support unix perms, oh well.
        pass
    return CRED_PATH


def clear_api_key() -> None:
    """Remove the saved key file."""
    if CRED_PATH.exists():
        CRED_PATH.unlink()
