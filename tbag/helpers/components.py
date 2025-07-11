"""
tbag.helpers.components
───────────────────────
CRUD helpers for the global *Components Library*.

Each component lives in   …/tbag/components/<cid>/
  ├─ config.json      { "name": "Pump", "gpio": 17, "image": "foo.png" }
  └─ images/          (optional preview pictures)
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

# 17 plain output pins we want to expose in the UI.
# Leave GPIO-20 / GPIO-21 free for the foot-pedal later on.
ALLOWED_GPIO_PINS: List[int] = [
    4, 5, 6,
    12, 13, 16, 17, 18, 19,
    22, 23, 24, 25, 26,
    10, 9, 11
]

# ────────────────────────── helpers ──────────────────────────────
def components_list() -> List[pathlib.Path]:
    """Return every component folder (Path objects) sorted A->Z."""
    return sorted(
        (d for d in COMPONENTS.iterdir() if d.is_dir()),
        key=lambda p: p.name.lower()
    )


def load_component(cid: str) -> Optional[Dict]:
    """Read `<COMPONENTS>/<cid>/config.json` or None if missing."""
    cfg = COMPONENTS / cid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None


def save_component(cid: str, data: Dict) -> None:
    """
    Write `<cid>/config.json` and ensure `images/` exists.

    If a *gpio* field is present it must be an int from
    ``ALLOWED_GPIO_PINS``.
    """
    if "gpio" in data:
        gpio = int(data["gpio"])
        if gpio not in ALLOWED_GPIO_PINS:
            raise ValueError(
                f"GPIO {gpio} not allowed – choose from {ALLOWED_GPIO_PINS}"
            )
        data["gpio"] = gpio                         # ensure it’s an int

    root = COMPONENTS / cid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as f:
        json.dump(data, f, indent=2)


def new_component_slug(name: str) -> str:
    """Human name → filesystem-friendly slug (fallback: short uuid)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:40]
    return slug or uuid.uuid4().hex[:6]


# ────────────────────────── exports ──────────────────────────────
__all__ = [
    "COMPONENTS",
    "ALLOWED_GPIO_PINS",
    "components_list",
    "load_component",
    "save_component",
    "new_component_slug",
]
