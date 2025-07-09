"""
Central configuration – **only paths & constants** live here.

We keep two base folders:

ROOT_DIR   – the repository root (one level above the tbag package)
PKG_DIR    – the *tbag* package directory itself

Projects now live in  “tbag/projects/” so they stay with the codebase,
but are still ignored by Git via .gitignore.
"""

from __future__ import annotations
import os
from pathlib import Path

# ─────────────────────────────────────────── directory layout
PKG_DIR  = Path(__file__).resolve().parent           # …/tbag
ROOT_DIR = PKG_DIR.parent                            # repo root

PROJECTS = PKG_DIR / "projects"                      # ← moved here
PROJECTS.mkdir(exist_ok=True)

DB_FILE  = ROOT_DIR / "events.db"                    # live DB

# ─────────────────────────────────────────── app constants
SECRET    = os.getenv("TBAG_SECRET",  "change-this-in-prod")
DEVICE_ID = os.getenv("TBAG_DEVICE",  "glovebox-pi")

__all__ = [
    "PROJECTS",
    "DB_FILE",
    "SECRET",
    "DEVICE_ID",
]
