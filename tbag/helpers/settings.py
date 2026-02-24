
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
    },
    "led_mapping": {
        "P1": 2, "P2": 3, "P3": 4, "P4": 17, "P5": 27,
        "P6": 22, "P7": 10, "P8": 9, "P9": 11, "P10": 0,
        "P21": 7, "P22": 8
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
            
            # Deep merge teachpoints
            if "teachpoints" in data:
                 for k, v in data["teachpoints"].items():
                     if k in merged["teachpoints"]:
                         merged["teachpoints"][k] = v
            
            # Deep merge led_mapping
            if "led_mapping" in data:
                for k, v in data["led_mapping"].items():
                    if k in merged["led_mapping"]:
                        merged["led_mapping"][k] = v
            
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
