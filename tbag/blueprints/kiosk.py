# ─── tbag/blueprints/kiosk.py ────────────────────────────────────────────
from __future__ import annotations

import sqlite3
import datetime
from flask import Blueprint, jsonify, render_template, request, abort

from ..helpers.projects import load_config
from ..db     import DB_FILE, log
from ..config import DEVICE_ID
from ..gpio   import LED, Button

bp = Blueprint("kiosk", __name__)
red_led, pedal = LED(17), Button(27)


# ── root page -----------------------------------------------------------
@bp.route("/")
def index():
    return render_template("index.html")


# ── queue API -----------------------------------------------------------
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


# ── progress / finish / abort ------------------------------------------
@bp.post("/api/progress")
def progress():
    """
    Handles 'next', 'finish', 'abort'.
    We first complete the UPDATE on 'runs', commit it, THEN call log() so the
    second write happens after the write-lock is released.
    """
    data = request.get_json(force=True)
    sid  = data["session_id"]
    act  = data["action"]
    now  = datetime.datetime.now().isoformat(timespec="seconds")

    if act == "next":
        red_led.toggle()
        log("next_pressed", {"session_id": sid})
        return jsonify(status="ok")

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

        changed = cur.rowcount
        conn.commit()               # <── RELEASE write-lock *before* log()

    if changed == 0:
        print(f"[WARN] progress '{act}' ignored: session {sid!r} not active",
              flush=True)

    # write to events table *after* the transaction above has finished
    if act == "finish":
        log("session_end",   {"session_id": sid})
    elif act == "abort":
        log("session_abort", {"session_id": sid, "step": data.get("step")})

    return jsonify(status=act)


# ── session overview page ----------------------------------------------
@bp.route("/session/<sid>")
def session_overview(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        run = c.execute("SELECT * FROM runs WHERE session_id = ?", (sid,)).fetchone()

    if run is None:
        abort(404, "session not found")

    cfg         = load_config(run["project"]) or {"sequence": []}
    total_steps = len(cfg["sequence"])

    return render_template("summary.html",
                           run=run,
                           total_steps=total_steps)


# ── tiny helper used by JS ---------------------------------------------
@bp.get("/pedal")
def pedal_state():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))
