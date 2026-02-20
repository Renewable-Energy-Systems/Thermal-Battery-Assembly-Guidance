
import json
import os
from ..config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "teachpoints": {
        "P1": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P2": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P3": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P4": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P5": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P6": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P7": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P8": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P9": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P10": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P21": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
        "P22": {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0},
    }
}

def load_settings():
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            # Merge with defaults
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            if "teachpoints" in data:
                 for k, v in data["teachpoints"].items():
                     if k in merged["teachpoints"]:
                         merged["teachpoints"][k] = v
            return merged
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False
