#!/usr/bin/env python3
"""Offline-first Flask app for Thermal-Battery Assembly Guidance."""

import os, sys, datetime, sqlite3, pathlib
from flask import Flask, render_template, jsonify

# ── GPIOZero import with safe fallback ────────────────────────────────────────
try:
    from gpiozero import LED, Button, Device
    # On non-Pi hosts force the mock back-end so no BadPinFactory is raised
    if not (sys.platform.startswith("linux") and os.path.exists("/proc/cpuinfo")):
        from gpiozero.pins.mock import MockFactory
        Device.pin_factory = MockFactory()          # ⚑ Development PC
except ImportError:
    # gpiozero isn't installed – make no-op stand-ins so the UI can load
    class _Dummy:
        def __init__(self, *_, **__): pass
        def on(self): pass
        def off(self): pass
        def toggle(self): pass
        @property
        def is_active(self): return False
    LED = Button = _Dummy                           # type: ignore

# ── App & DB bootstrap ───────────────────────────────────────────────────────
DB_PATH = pathlib.Path(__file__).with_name("events.db")
app = Flask(__name__)

red_led = LED(17)          # Status / guidance LED
pedal   = Button(27)       # Foot-pedal switch

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS events (
                   ts    TEXT,
                   event TEXT
               )"""
        )
init_db()

def log(event: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO events VALUES (?, ?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), event),
        )

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/next", methods=["POST"])
def next_step():
    red_led.toggle()
    log("next_pressed")
    return jsonify(status="ok")

@app.route("/pedal")
def pedal_status():
    # works on Pi (real input) and on PC (always False in mock)
    return jsonify(pressed=pedal.is_active)

# ── Dev entry-point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
