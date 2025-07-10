# ─── tbag/blueprints/kiosk.py ────────────────────────────────────────────
from __future__ import annotations
import sqlite3, datetime, threading, time
from flask import Blueprint, jsonify, render_template, request, abort

from ..helpers.projects   import load_config
from ..helpers.components import load_component
from ..db   import DB_FILE, log
from ..config import DEVICE_ID
from ..gpio  import LED, Button     # safe wrapper – mocks on PC

bp = Blueprint("kiosk", __name__)

# cache LED objects so we only claim a pin once
_led_cache: dict[int, LED] = {}
def _led(pin: int) -> LED:
    if pin not in _led_cache:
        _led_cache[pin] = LED(pin)
    return _led_cache[pin]

# leave foot-pedal on 20/21 for later
pedal = Button(20) if hasattr(Button, "__call__") else Button()

# ───────────────────────── UI pages ────────────────────────
@bp.route("/")
def index():
    return render_template("index.html")

# ───────────────────────── queue feed ──────────────────────
@bp.get("/api/pending")
def pending():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT session_id,project,stack_id,operator,ts_created "
            "FROM runs WHERE status='pending' ORDER BY ts_created"
        ).fetchall()
    return jsonify([dict(r) for r in rows])

# ───────────────────────── claim session ───────────────────
@bp.post("/api/claim")
def claim():
    data = request.json or {}
    sid  = data.get("session_id")
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

# ───────────────────────── progress / finish / abort ───────
@bp.post("/api/progress")
def progress():
    """
    Expects JSON: {session_id, action, step?, component?}
    For “next” we blink the component’s LED once (0.3 s).
    """
    data = request.get_json(force=True)
    sid  = data["session_id"]
    act  = data["action"]
    now  = datetime.datetime.now().isoformat(timespec="seconds")

    # —— NEXT ————————————————————————————————
    if act == "next":
        comp_id = data.get("component")
        if comp_id:
            comp = load_component(comp_id)
            if comp:
                led = _led(int(comp["gpio"]))
                threading.Thread(
                    target=lambda l=led: (l.on(), time.sleep(0.3), l.off()),
                    daemon=True).start()
        log("next_pressed", {"session_id": sid, "component": comp_id})
        return jsonify(status="ok")

    # —— FINISH / ABORT ——————————————————————————
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()

        if act == "finish":
            cur.execute(
                """
                UPDATE runs
                   SET status      = 'finished',
                       ts_finished = ?
                 WHERE session_id  = ? AND status = 'active'
                """,
                (now, sid)
            )

        elif act == "abort":
            cur.execute(
                """
                UPDATE runs
                   SET status        = 'aborted',
                       ts_finished   = ?,
                       interrupted_at= ?
                 WHERE session_id    = ? AND status = 'active'
                """,
                (now, data.get("step"), sid)
            )

        conn.commit()

    if act == "finish":
        log("session_end",   {"session_id": sid})
    elif act == "abort":
        log("session_abort", {"session_id": sid, "step": data.get("step")})

    return jsonify(status=act)

# ───────────────────────── pedal helper ─────────────────────
@bp.get("/pedal")
def pedal_state():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))
