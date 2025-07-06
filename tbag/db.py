import sqlite3, datetime
from .config import DB_FILE

_SCHEMA = """
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
"""

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def migrate() -> None:
    with connect() as c:
        c.executescript(_SCHEMA)

def log(event:str) -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with connect() as c:
        c.execute("INSERT INTO events VALUES(?,?)", (ts, event))
