"""
tbag.components_helpers
────────────────────────
Tiny helper-module that keeps the *Components Library* on disk.

Each component lives in            …/tbag/components/<cid>/
  ├─ config.json   {"name": "...", "label": "L7", "img": "foo.png"}
  └─ images/       (uploaded pictures)

Now also exports:
• ALLOWED_GPIO_PINS – ordered BCM pins behind L1…L23
• GPIO_LABELS       – {2: "L1", …}
• LABEL_TO_GPIO     – {"L1": 2, …}
"""

from __future__ import annotations
import json, pathlib, uuid, re
from typing import Dict, List, Optional

# ────────────────────────── constants ────────────────────────────
BASE_DIR   = pathlib.Path(__file__).resolve().parent
COMPONENTS = BASE_DIR / "components"
COMPONENTS.mkdir(exist_ok=True)

ALLOWED_GPIO_PINS: List[int] = [
    2, 3, 4, 17, 27, 22, 10, 9, 11, 0, 5, 6,
    13, 19, 26, 21, 20, 16, 12, 1, 7, 8, 25,      # L1…L23
]

GPIO_LABELS: Dict[int, str] = {pin: f"L{idx+1}"
                               for idx, pin in enumerate(ALLOWED_GPIO_PINS)}
LABEL_TO_GPIO: Dict[str, int] = {lbl: pin for pin, lbl in GPIO_LABELS.items()}

# ────────────────────────── helpers ──────────────────────────────
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
    """
    Write config.json and ensure images/ exists.

    Expect either “label” (e.g. "L7") or “gpio” (int/Bcm number).
    Validate against ALLOWED_GPIO_PINS and store **label** form.
    """
    # normalise / validate pin reference
    if "label" in data:
        lbl = data["label"]
        if lbl not in LABEL_TO_GPIO:
            raise ValueError(f"Bad label {lbl!r}; choose one of {list(LABEL_TO_GPIO)}")
    elif "gpio" in data:
        pin = int(data["gpio"])
        if pin not in ALLOWED_GPIO_PINS:
            raise ValueError(f"GPIO {pin} not allowed – choose from {ALLOWED_GPIO_PINS}")
        data["label"] = GPIO_LABELS[pin]      # store canonical label
        data.pop("gpio", None)
    else:
        raise ValueError("Must supply either 'label' or 'gpio'")

    root = COMPONENTS / cid
    (root / "images").mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("w") as fh:
        json.dump(data, fh, indent=2)


def new_component_slug(name: str) -> str:
    """Slugify *or* fall back to a random id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:40]
    return slug or uuid.uuid4().hex[:6]

# ────────────────────────── exports ──────────────────────────────
__all__ = [
    "ALLOWED_GPIO_PINS",
    "GPIO_LABELS",
    "LABEL_TO_GPIO",
    "list_components",
    "load_component",
    "save_component",
    "new_component_slug",
]
