"""
tbag.helpers.components
───────────────────────
CRUD helpers for the global *Components Library*.

Each component lives in   …/tbag/components/<cid>/
  ├─ config.json      { "name": "Pump", "gpio": 17, "image": "foo.png" }
  └─ images/          (optional preview pictures)

This version introduces:

• 23 ordered GPIOs that match your D-SUB layout (L1…L23)  
• GPIO_LABELS -> {2: "L1", 3: "L2", … 25: "L23"} for friendlier UIs
"""

from __future__ import annotations

import json
import pathlib
import re
import uuid
from typing import Dict, List, Optional

# ────────────────────────── constants ────────────────────────────
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent          # …/tbag
COMPONENTS = BASE_DIR / "components"
COMPONENTS.mkdir(exist_ok=True)

# 23 plain output pins exposed to the user (ordered L1 → L23)
ALLOWED_GPIO_PINS: List[int] = [
    2,   # L1
    3,   # L2
    4,   # L3
    17,  # L4
    27,  # L5
    22,  # L6
    10,  # L7
    9,   # L8
    11,  # L9
    0,   # L10
    5,   # L11
    6,   # L12
    13,  # L13
    19,  # L14
    26,  # L15
    21,  # L16
    20,  # L17
    16,  # L18
    12,  # L19
    1,   # L20
    7,   # L21
    8,   # L22
    25,  # L23
]

# Human-friendly labels — handy for drop-downs, logs, etc.
GPIO_LABELS: Dict[int, str] = {
    pin: f"L{idx + 1}" for idx, pin in enumerate(ALLOWED_GPIO_PINS)
}

# ────────────────────────── helpers ──────────────────────────────
def components_list() -> List[pathlib.Path]:
    """Return every component folder (Path objects) sorted A → Z."""
    return sorted(
        (d for d in COMPONENTS.iterdir() if d.is_dir()),
        key=lambda p: p.name.lower(),
    )


def load_component(cid: str) -> Optional[Dict]:
    """Read `<COMPONENTS>/<cid>/config.json`; return None if missing."""
    cfg = COMPONENTS / cid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None


def save_component(cid: str, data: Dict) -> None:
    """
    Write `<cid>/config.json` and ensure `images/` exists.

    If a *gpio* field is present it must be an int in ``ALLOWED_GPIO_PINS``.
    """
    if "gpio" in data:
        gpio = int(data["gpio"])
        if gpio not in ALLOWED_GPIO_PINS:
            raise ValueError(
                f"GPIO {gpio} not allowed – choose from {ALLOWED_GPIO_PINS}"
            )
        data["gpio"] = gpio  # ensure JSON stores an int, not a string

    root = COMPONENTS / cid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as f:
        json.dump(data, f, indent=2)


def new_component_slug(name: str) -> str:
    """Convert *name* → filesystem-friendly slug (fallback: short UUID)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:40]
    return slug or uuid.uuid4().hex[:6]


# ────────────────────────── exports ──────────────────────────────
__all__ = [
    "COMPONENTS",
    "ALLOWED_GPIO_PINS",
    "GPIO_LABELS",
    "components_list",
    "load_component",
    "save_component",
    "new_component_slug",
]
