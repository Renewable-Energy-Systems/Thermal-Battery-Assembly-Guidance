# tbag/config.py
import pathlib, os

BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent
PROJECTS   = BASE_DIR / "projects"
DB_FILE    = BASE_DIR / "events.db"

SECRET     = os.getenv("TBAG_SECRET", "change-this-in-prod")
DEVICE_ID  = os.getenv("TBAG_DEVICE", "glovebox-pi")
