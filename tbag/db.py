"""DB initialisation & small helpers."""
import sqlite3, datetime, json
from tbag.config import DB_FILE          # path comes from config.py

# ── bootstrap ────────────────────────────────────────────────────────────
def init() -> None:
    with sqlite3.connect(DB_FILE) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS events(
          ts    TEXT,
          event TEXT
        );
        CREATE TABLE IF NOT EXISTS runs(
          session_id     TEXT PRIMARY KEY,
          project        TEXT,
          stack_id       TEXT,
          operator       TEXT,
          ts_created     TEXT,
          ts_started     TEXT,
          ts_finished    TEXT,
          status         TEXT CHECK(status IN
                        ('pending','active','finished','aborted')),
          interrupted_at INTEGER,
          device         TEXT
        );
        """)

# ── public helpers ───────────────────────────────────────────────────────
def connect() -> sqlite3.Connection:
    """Return a *new* connection to the TBAG SQLite DB."""
    return sqlite3.connect(DB_FILE)

def log(event: str, payload: dict | None = None) -> None:
    """Append a row to the `events` table."""
    blob = event if payload is None else f"{event}::{json.dumps(payload)}"
    with connect() as c:
        c.execute(
            "INSERT INTO events VALUES(?,?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), blob)
        )

# run bootstrap once on import
init()
