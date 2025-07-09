"""
tbag.helpers.projects
─────────────────────
Canonical helper layer for project “recipes”.

• Keeps a single `PROJECTS` directory reference that every blueprint uses
• Falls back to the repository-top-level “projects/” folder if it already
  exists or contains data (so older deployments continue to work)
• No self-import ⇒ no circular-import crash
"""

from __future__ import annotations
import json, pathlib, uuid
from typing import Dict, List, Optional

# ── decide which folder to use ───────────────────────────────────────────
_PKG_ROOT   = pathlib.Path(__file__).resolve().parent.parent      # …/tbag
_BASE_ROOT  = _PKG_ROOT.parent                                    # repo root

_TOPLEVEL   = _BASE_ROOT / "projects"         # legacy location
_PACKAGELOC = _PKG_ROOT / "projects"          # new default

def _choose_projects_dir() -> pathlib.Path:
    """Return the folder that actually stores project configs."""
    # Use legacy folder if it already contains *anything* – keeps old data
    try:
        if (_TOPLEVEL.exists() and                 # real dir
            (any(_TOPLEVEL.iterdir())              # ─or─ has files/dirs
             or (_TOPLEVEL / "config.json").exists())):
            return _TOPLEVEL
    except FileNotFoundError:
        pass                                       # nothing there, fall back
    return _PACKAGELOC

PROJECTS: pathlib.Path = _choose_projects_dir()
PROJECTS.mkdir(exist_ok=True)                     # ensure it exists

# ── helper functions (NO Flask imports here) ─────────────────────────────
def projects_list() -> List[pathlib.Path]:
    """Return every project folder, sorted A->Z (case-insensitive)."""
    return sorted(
        (d for d in PROJECTS.iterdir() if d.is_dir()),
        key=lambda p: p.name.lower()
    )


def load_config(pid: str) -> Optional[Dict]:
    """Read <PROJECTS>/<pid>/config.json or return None."""
    cfg = PROJECTS / pid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None


def save_config(pid: str, data: Dict) -> None:
    """Write the config (creates images/ if needed)."""
    root = PROJECTS / pid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as f:
        json.dump(data, f, indent=2)


def new_project_slug(name: str) -> str:
    """Turn ‘Nice Name’ into `nice_name` – or fallback to random id."""
    slug = name.replace(" ", "_").lower()[:40]
    return slug or uuid.uuid4().hex[:6]


__all__ = [
    "PROJECTS",
    "projects_list",
    "load_config",
    "save_config",
    "new_project_slug",
]
