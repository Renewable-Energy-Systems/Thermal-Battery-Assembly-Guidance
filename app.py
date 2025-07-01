#!/usr/bin/env python3
"""Offline‑first Flask app for Thermal‑Battery Assembly Guidance"""

# ── Standard library ─────────────────────────────────────────────────────────
import os, sys, json, uuid, datetime, sqlite3, pathlib

# ── Flask ────────────────────────────────────────────────────────────────────
from flask import (
    Flask,
    render_template,
    jsonify,
    redirect,
    request,
    session,
)

# ── GPIOZero with automatic mock fallback for dev PCs ───────────────────────
try:
    from gpiozero import LED, Button, Device

    # Switch to mock backend automatically on non‑Pi hosts
    if not (sys.platform.startswith("linux") and os.path.exists("/proc/cpuinfo")):
        from gpiozero.pins.mock import MockFactory

        Device.pin_factory = MockFactory()
except ImportError:  # gpiozero not installed on this host

    class _Dummy:  # minimal stand‑in so code runs on any OS
        def __init__(self, *_, **__):
            pass

        def on(self):
            pass

        def off(self):
            pass

        def toggle(self):
            pass

        @property
        def is_active(self):
            return False

    LED = Button = _Dummy  # type: ignore

# ── Paths & constants ────────────────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).parent
DB_PATH = BASE_DIR / "events.db"
PROJECTS_DIR = BASE_DIR / "projects"

# ── Flask app instance ───────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "change‑me‑to‑a‑secure‑random‑string"

# Disable template & static‑file caching during dev so edits appear instantly
app.config.update(
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,   # static files
)
app.jinja_env.auto_reload = True

# ── Hardware wiring (BCM numbers) ────────────────────────────────────────────
red_led = LED(17)
pedal = Button(27)

# ── SQLite bootstrap ─────────────────────────────────────────────────────────

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS events (
                   ts    TEXT,
                   event TEXT
               )"""
        )


def log(event: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO events VALUES (?, ?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), event),
        )


init_db()

# ── Helper: enumerate available projects ─────────────────────────────────────

def load_projects():
    projects = []
    for cfg in PROJECTS_DIR.glob("*/config.json"):
        with cfg.open() as f:
            meta = json.load(f)
        projects.append(
            {"id": cfg.parent.name, "name": meta.get("name", cfg.parent.name)}
        )
    return sorted(projects, key=lambda p: p["name"].lower())


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/select")
def select_project():
    return render_template("project_select.html", projects=load_projects())


@app.post("/start")
def start_session():
    data = {
        "session_id": str(uuid.uuid4())[:8],
        "project": request.form["project"],
        "stack_id": request.form["stack_id"],
        "operator": request.form["operator"],
        "timestamp": request.form["timestamp"],
    }
    session["run"] = data
    log(f"session_start::{json.dumps(data)}")
    return redirect("/")


@app.route("/")
def index():
    if "run" not in session:
        return redirect("/select")
    return render_template("index.html")


@app.route("/next", methods=["POST"])
def next_step():
    red_led.toggle()
    log("next_pressed")
    return jsonify(status="ok")


@app.route("/pedal")
def pedal_status():
    return jsonify(pressed=pedal.is_active)


# ── Dev entry‑point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # debug=True enables Flask reloader so code edits auto‑reload server
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=True)
