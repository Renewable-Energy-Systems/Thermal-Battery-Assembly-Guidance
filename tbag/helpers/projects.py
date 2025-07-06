"""
tbag.helpers.projects
─────────────────────
Utility functions shared by the blueprints.
"""

from __future__ import annotations
import json, pathlib, uuid
from typing import List, Dict, Optional

# path to “…/tbag/projects/”
BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent    # …/tbag
PROJECTS   = BASE_DIR / "projects"
PROJECTS.mkdir(exist_ok=True)

# ── helpers ──────────────────────────────────────────────────
def projects_list() -> List[pathlib.Path]:
    """Return every project folder sorted case-insensitively."""
    return sorted(
        (d for d in PROJECTS.iterdir() if d.is_dir()),
        key=lambda p: p.name.lower()
    )

def load_config(pid: str) -> Optional[Dict]:
    """Read <PROJECTS>/<pid>/config.json or None."""
    cfg = PROJECTS / pid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None

def save_config(pid: str, data: Dict) -> None:
    """Write config + make images/ dir."""
    root = PROJECTS / pid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as f:
        json.dump(data, f, indent=2)

def new_project_slug(name: str) -> str:
    """make “nice_name” → slug or random id if empty"""
    slug = name.replace(" ", "_").lower()[:40]
    return slug or uuid.uuid4().hex[:6]

__all__ = [
    "projects_list",
    "load_config",
    "save_config",
    "new_project_slug",
]
