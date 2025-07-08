"""
Pure helpers – no Flask import here.
"""
import json, uuid
from pathlib import Path
from typing import Dict, List, Optional
from tbag.config import PROJECTS

def all_dirs() -> List[Path]:
    return sorted((d for d in PROJECTS.iterdir() if d.is_dir()),
                  key=lambda p: p.name.lower())

def load(pid:str) -> Optional[Dict]:
    cfg = PROJECTS / pid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None

def save(pid:str, data:Dict) -> None:
    d = PROJECTS / pid
    (d / "images").mkdir(parents=True, exist_ok=True)
    with (d / "config.json").open("w") as f:
        json.dump(data, f, indent=2)

def new_id(human:str)->str:
    return (human.replace(" ", "_").lower()[:40] or uuid.uuid4().hex[:6])
