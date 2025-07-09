# tbag/blueprints/__init__.py
"""
Expose all blueprints so the main app can import them with
    from tbag.blueprints import kiosk, admin, components, projects, logs
"""

from . import (
    kiosk,
    admin,
    components,   # ← NEW
    projects,
    logs,
)

__all__ = [
    "kiosk",
    "admin",
    "components",
    "projects",
    "logs",
]
