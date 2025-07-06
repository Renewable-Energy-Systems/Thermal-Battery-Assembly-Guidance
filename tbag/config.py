from pathlib import Path
import os

BASE = Path(__file__).resolve().parent
PROJECTS = BASE / "projects"
PROJECTS.mkdir(exist_ok=True)

DB_FILE   = BASE / "events.db"
DEVICE_ID = os.getenv("TBAG_DEVICE", "glovebox-pi")
SECRET    = os.getenv("TBAG_SECRET", "change-me")      # TODO set in prod
