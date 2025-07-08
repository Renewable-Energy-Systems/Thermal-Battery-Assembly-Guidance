"""
tbag.components_helpers
────────────────────────
Tiny helper-module that keeps the *Components Library* on disk.
Each component lives in            …/tbag/components/<cid>/
  ├─ config.json   {"name": "...", "label": "...", "img": "foo.png"}
  └─ images/       (uploaded pictures)
"""

from __future__ import annotations
import json, pathlib, uuid
from typing import Dict, List, Optional

BASE_DIR    = pathlib.Path(__file__).resolve().parent
COMPONENTS  = BASE_DIR / "components"
COMPONENTS.mkdir(exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────
def list_components() -> List[Dict]:
    """Return every component’s JSON merged with its folder-name `id`."""
    comps: List[Dict] = []
    for d in sorted(COMPONENTS.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir():
            continue
        cfg_file = d / "config.json"
        if cfg_file.exists():
            cfg = json.load(cfg_file.open())
            cfg["id"] = d.name
            comps.append(cfg)
    return comps


def load_component(cid: str) -> Optional[Dict]:
    """config or None if missing"""
    f = COMPONENTS / cid / "config.json"
    return json.load(f.open()) if f.exists() else None


def save_component(cid: str, data: Dict) -> None:
    """Write config.json and ensure images/ exists."""
    root = COMPONENTS / cid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as fh:
        json.dump(data, fh, indent=2)


def new_component_slug(name: str) -> str:
    """Slugify *or* fall back to a random id."""
    slug = name.replace(" ", "_").lower()[:40]
    return slug or uuid.uuid4().hex[:6]


__all__ = [
    "list_components",
    "load_component",
    "save_component",
    "new_component_slug",
]
