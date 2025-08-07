"""
tbag.blueprints.kiosk
─────────────────────
Shop-floor runtime for the Raspberry Pi.
"""

from __future__ import annotations
import datetime, sqlite3, time
from typing import Dict, Optional
from flask import Blueprint, abort, jsonify, render_template, request

from ..config import DEVICE_ID
from ..db     import DB_FILE, log
from ..gpio   import LED, Button
from ..helpers.components import ALLOWED_GPIO_PINS, load_component
from ..helpers.projects    import load_config

# gpiod reset (unchanged) ------------------------------------------------
try:
    import gpiod                         # type: ignore
    _HAS_GPIOD = True
except ImportError:
    _HAS_GPIOD = False

# LED helpers (unchanged) ------------------------------------------------
_led_cache: Dict[int, LED] = {}
_current_pin: Optional[int] = None
def _led(pin:int)->LED:
    if pin not in _led_cache:
        _led_cache[pin]=LED(pin)
    return _led_cache[pin]
def _activate_led(pin:Optional[int])->None:
    global _current_pin
    if pin==_current_pin: return
    if _current_pin is not None:
        try:_led(_current_pin).off()
        finally:_led(_current_pin).close();_led_cache.pop(_current_pin,None)
    _current_pin=None
    if pin is not None:
        try:_led(pin).on();_current_pin=pin
        except Exception as exc:
            print(f"[WARN] cannot switch LED on GPIO {pin}: {exc}",flush=True)
            try:_led(pin).close()
            finally:_led_cache.pop(pin,None)
def _reset_all_leds()->None:
    for pin in ALLOWED_GPIO_PINS:
        if _HAS_GPIOD:
            try:
                chip=gpiod.Chip("gpiochip0");line=chip.get_line(pin)
                line.request(consumer="tbag-force-reset",
                             type=gpiod.LINE_REQ_DIR_OUT,default_vals=[0])
                time.sleep(0.005)
            except Exception: pass
            finally:
                try: line.release(), chip.close()
                except Exception: pass
        try: led=LED(pin);led.off();led.close()
        except Exception: pass
        _led_cache.pop(pin,None)
    global _current_pin; _current_pin=None

# Flask blueprint -------------------------------------------------------
bp = Blueprint("kiosk", __name__)
pedal = Button(20) if hasattr(Button,"__call__") else Button()

@bp.route("/")
def index():                       # inject fixed id for the Pi kiosk
    return render_template("index.html", device_id="local-pi")

@bp.get("/api/pending")
def pending():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory=sqlite3.Row
        rows=c.execute(
            """
            SELECT session_id,project,stack_id,operator,ts_created
            FROM runs
            WHERE status='pending'
              AND (device IS NULL OR device = '' OR device='local-pi')
            ORDER BY ts_created
            """).fetchall()
    return jsonify([dict(r) for r in rows])

# ── ONLY LOCALHOST MAY CLAIM ───────────────────────────────────────────
@bp.post("/api/claim")
def claim():
    # Only the *local* Chromium (opened as http://127.0.0.1:8000) may claim
    if not (
        request.remote_addr in ("127.0.0.1", "::1")
        and request.host.startswith("127.0.0.1")
    ):
        abort(403, "Only the kiosk running on the Pi can claim a session.")

    sid = (request.json or {}).get("session_id")
    if not sid:
        abort(400, "session_id missing")

    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        run = c.execute(
            """
            UPDATE runs
               SET status     = 'active',
                   ts_started = ?,
                   device     = 'local-pi'
             WHERE session_id = ?
               AND status     = 'pending'
               AND (device IS NULL OR device = '' OR device = 'local-pi')
            RETURNING *
            """,
            (datetime.datetime.now().isoformat(timespec="seconds"), sid),
        ).fetchone()

    if run is None:
        abort(409, "session already claimed or not found")

    _reset_all_leds()
    cfg = load_config(run["project"]) or {"sequence": []}
    return jsonify(status="claimed",
                   session=dict(run),
                   sequence=cfg["sequence"])


# -------- progress / finish / abort (unchanged) -------------------------
@bp.post("/api/progress")
def progress():
    data = request.get_json(force=True)
    sid  = data["session_id"]
    act  = data["action"]
    now  = datetime.datetime.now().isoformat(timespec="seconds")

    if act == "next":
        comp_id = data.get("component")
        if comp_id:
            comp = load_component(comp_id)
            if comp and comp.get("gpio") not in (None, ""):
                try:
                    _activate_led(int(comp["gpio"]))
                except ValueError:
                    print(f"[WARN] non-numeric GPIO in {comp_id}", flush=True)

        log("next_pressed", {"session_id": sid, "component": comp_id})
        return jsonify(status="ok")

    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        if act == "finish":
            cur.execute(
                "UPDATE runs SET status='finished', ts_finished=? "
                "WHERE session_id=? AND status='active'",
                (now, sid),
            )
        elif act == "abort":
            cur.execute(
                "UPDATE runs SET status='aborted', ts_finished=?, interrupted_at=? "
                "WHERE session_id=? AND status='active'",
                (now, data.get("step"), sid),
            )
        conn.commit()

    _reset_all_leds()
    log("session_end" if act == "finish" else "session_abort",
        {"session_id": sid, "step": data.get("step")} if act == "abort" else {"session_id": sid})
    return jsonify(status=act)

# -------- summary page --------------------------------------------------
@bp.route("/session/<sid>")
def session_overview(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        run = c.execute("SELECT * FROM runs WHERE session_id=?", (sid,)).fetchone()
    if run is None:
        abort(404, "session not found")
    cfg = load_config(run["project"]) or {"sequence": []}
    return render_template("summary.html", run=run, total_steps=len(cfg["sequence"]))

# -------- pedal helper (unchanged) -------------------------------------
@bp.get("/pedal")
def pedal_state():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))
