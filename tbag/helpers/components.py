"""
tbag.helpers.components
───────────────────────
CRUD helpers for the global *component* library.
"""

from __future__ import annotations
import json, pathlib, uuid
from typing import List, Dict, Optional

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent   # …/tbag
COMPONENTS = BASE_DIR / "components"
COMPONENTS.mkdir(exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────
def components_list() -> List[pathlib.Path]:
    """Return every component folder sorted case-insensitively."""
    return sorted(
        (d for d in COMPONENTS.iterdir() if d.is_dir()),
        key=lambda p: p.name.lower()
    )


def load_component(cid: str) -> Optional[Dict]:
    """Read <COMPONENTS>/<cid>/config.json or None."""
    cfg = COMPONENTS / cid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None


def save_component(cid: str, data: Dict) -> None:
    """Write config + make images/ dir."""
    root = COMPONENTS / cid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as f:
        json.dump(data, f, indent=2)


def new_component_slug(name: str) -> str:
    """Convert a human name → slug; fall back to a short uuid."""
    slug = name.replace(" ", "_").lower()[:40]
    return slug or uuid.uuid4().hex[:6]


__all__ = [
    "COMPONENTS",
    "components_list",
    "load_component",
    "save_component",
    "new_component_slug",
]
