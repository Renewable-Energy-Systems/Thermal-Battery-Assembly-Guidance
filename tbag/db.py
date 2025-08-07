"""DB initialisation & small helpers."""
from __future__ import annotations

import datetime
import json
import sqlite3

from tbag.config import DB_FILE, DEVICE_ID

# ───────────────────────── bootstrap ────────────────────────────────────
def init() -> None:
    with sqlite3.connect(DB_FILE) as c:
        c.executescript(
            """
            /* event log */
            CREATE TABLE IF NOT EXISTS events(
              ts    TEXT,
              event TEXT
            );

            /* run queue */
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

            /* manually registered, permanent devices */
            CREATE TABLE IF NOT EXISTS devices(
              device_id   TEXT PRIMARY KEY,
              description TEXT,
              ts_added    TEXT
            );

            /* presence-based devices: auto-add / auto-expire */
            CREATE TABLE IF NOT EXISTS devices_presence(
              device_id TEXT PRIMARY KEY,
              last_seen TEXT
            );
            """
        )

        # auto-insert this Pi as a *permanent* device (idempotent)
        c.execute(
            """INSERT OR IGNORE INTO devices(device_id, description, ts_added)
               VALUES(?, 'Auto-added at first boot', ?)""",
            (DEVICE_ID, datetime.datetime.now().isoformat(timespec="seconds")),
        )

# ──────────────────────── helpers / public API ──────────────────────────
def connect() -> sqlite3.Connection:
    """Return a *new* connection to the TBAG SQLite DB."""
    return sqlite3.connect(DB_FILE)


def log(event: str, payload: dict | None = None) -> None:
    """Append a row to `events`."""
    blob = event if payload is None else f"{event}::{json.dumps(payload)}"
    with connect() as c:
        c.execute(
            "INSERT INTO events VALUES(?,?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), blob),
        )


# presence helpers
_PRESENCE_TIMEOUT_SEC = 120   # 2-minute grace

def touch_presence(device_id: str) -> None:
    """Insert/update a presence heartbeat."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with connect() as c:
        c.execute(
            """INSERT INTO devices_presence(device_id, last_seen)
               VALUES(?, ?)
               ON CONFLICT(device_id) DO UPDATE SET last_seen=excluded.last_seen""",
            (device_id, now),
        )


def remove_presence(device_id: str) -> None:
    with connect() as c:
        c.execute("DELETE FROM devices_presence WHERE device_id=?", (device_id,))


def current_presence() -> list[str]:
    """Return device_ids seen in the last `_PRESENCE_TIMEOUT_SEC` seconds."""
    cutoff = (
        datetime.datetime.now() - datetime.timedelta(seconds=_PRESENCE_TIMEOUT_SEC)
    ).isoformat(timespec="seconds")
    with connect() as c:
        rows = c.execute(
            "SELECT device_id FROM devices_presence WHERE last_seen >= ?", (cutoff,)
        ).fetchall()
    return [r[0] for r in rows]


# bootstrap at import time
init()
