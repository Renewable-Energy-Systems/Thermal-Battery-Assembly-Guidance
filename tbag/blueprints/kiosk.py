# ─── tbag/blueprints/kiosk.py ───────────────────────────────────────────
from __future__ import annotations

import datetime, sqlite3, threading, time
from flask import Blueprint, abort, jsonify, render_template, request

from ..config           import DEVICE_ID
from ..db               import DB_FILE, log
from ..gpio             import LED, Button           # mocked automatically on PC
from ..helpers.projects import load_config
from ..helpers.components import load_component

bp = Blueprint("kiosk", __name__)

# ── LED handling ────────────────────────────────────────────────────────
_led_cache: dict[int, LED] = {}          # 1 LED obj per pin

def _led(pin: int) -> LED:
    if pin not in _led_cache:
        _led_cache[pin] = LED(pin)
    return _led_cache[pin]

def _blink(pin: int, dur: float = .3):
    """Switch the pin ON for <dur> seconds in a background thread."""
    led = _led(pin)
    threading.Thread(
        target=lambda l=led: (l.on(), time.sleep(dur), l.off()),
        daemon=True
    ).start()

def _reset_all_leds():
    """Turn **everything** off and release the pins."""
    for led in _led_cache.values():
        try:
            led.off()
            led.close()
        except Exception:
            pass
    _led_cache.clear()

# ── foot pedal (GPIO-21)  – mocked on non-Pi systems ───────────────────
pedal = Button(21) if hasattr(Button, "__call__") else Button()

# ── UI root ─────────────────────────────────────────────────────────────
@bp.get("/")
def index():
    return render_template("index.html")

# ── queue helpers used by JS  ───────────────────────────────────────────
@bp.get("/api/pending")
def pending():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT session_id,project,stack_id,operator,ts_created "
            "FROM runs WHERE status='pending' ORDER BY ts_created"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.post("/api/claim")
def claim():
    sid = (request.json or {}).get("session_id")
    if not sid:
        abort(400, "session_id missing")

    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        cur = c.execute(
            """
            UPDATE runs
               SET status     = 'active',
                   ts_started = ?,
                   device     = ?
             WHERE session_id = ? AND status = 'pending'
            RETURNING *
            """,
            (datetime.datetime.now().isoformat(timespec="seconds"),
             DEVICE_ID,
             sid)
        )
        run = cur.fetchone()

    if run is None:
        abort(409, "session already claimed or not found")

    cfg = load_config(run["project"]) or {"sequence": []}
    return jsonify(status="claimed",
                   session=dict(run),
                   sequence=cfg["sequence"])

# ── progress / finish / abort  ──────────────────────────────────────────
@bp.post("/api/progress")
def progress():
    """
    Receives JSON { session_id, action, step?, component? }.

    * `"next"`    – blink that component’s LED once
    * `"finish"`  – mark run finished, turn **all** LEDs off
    * `"abort"`   – mark run aborted  , turn **all** LEDs off
    """
    data = request.get_json(force=True)
    sid, act = data["session_id"], data["action"]
    now      = datetime.datetime.now().isoformat(timespec="seconds")

    # ---- NEXT  ---------------------------------------------------------
    if act == "next":
        comp_id = data.get("component")
        if comp_id:
            comp = load_component(comp_id)
            if comp and "gpio" in comp:
                _blink(int(comp["gpio"]))
        log("next_pressed", {"session_id": sid, "component": comp_id})
        return jsonify(status="ok")

    # ---- FINISH / ABORT  ----------------------------------------------
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()

        if act == "finish":
            cur.execute(
                """UPDATE runs
                      SET status='finished', ts_finished=?
                    WHERE session_id=? AND status='active'""",
                (now, sid)
            )
        elif act == "abort":
            cur.execute(
                """UPDATE runs
                      SET status='aborted', ts_finished=?, interrupted_at=?
                    WHERE session_id=? AND status='active'""",
                (now, data.get("step"), sid)
            )

        conn.commit()

    # make absolutely sure no LEDs are left on
    _reset_all_leds()

    # log event after tx finished
    if act == "finish":
        log("session_end",   {"session_id": sid})
    elif act == "abort":
        log("session_abort", {"session_id": sid, "step": data.get("step")})

    return jsonify(status=act)

# ── summary page  ───────────────────────────────────────────────────────
@bp.get("/session/<sid>")
def session_overview(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        run = c.execute(
            "SELECT * FROM runs WHERE session_id = ?", (sid,)
        ).fetchone()

    if run is None:
        abort(404, "session not found")

    cfg         = load_config(run["project"]) or {"sequence": []}
    total_steps = len(cfg["sequence"])

    return render_template(
        "summary.html",
        run=run,
        total_steps=total_steps
    )

# ── tiny helper for the pedal widget  -----------------------------------
@bp.get("/pedal")
def pedal_state():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))
