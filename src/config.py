"""
PO Management Tool — Configuration & Settings

Centralized constants, default values, and user settings persistence.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

# ===== Application Constants =====
APP_NAME = "PO Management Tool"
APP_VERSION = "2.1.0"
LOGFILE = "po_merge_tool.log"
DEFAULT_PATTERN = r"\bSG\d{4}\b"

# ===== Settings Persistence =====
# Store settings next to the executable / script
_SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", "."), "LPA_POP")
SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")


def resource_path(rel_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        # Development mode: resolve relative to project root (parent of src/)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, rel_path)


@dataclass
class AppSettings:
    """Persisted user preferences (last used paths, window state, theme, etc.)."""
    last_input_paths: List[str] = field(default_factory=list)
    last_list_file: str = ""
    last_output_dir: str = ""
    window_width: int = 1050
    window_height: int = 700
    theme_mode: str = "dark"  # "dark", "light", "system"
    color_theme: str = "blue"  # "blue", "green", "dark-blue"
    custom_pattern: str = DEFAULT_PATTERN

    # --- Serialization ---
    def save(self, path: str = SETTINGS_FILE) -> None:
        """Write settings to JSON file."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Non-critical — silently ignore save failures

    @classmethod
    def load(cls, path: str = SETTINGS_FILE) -> "AppSettings":
        """Load settings from JSON file, returning defaults on failure."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()
