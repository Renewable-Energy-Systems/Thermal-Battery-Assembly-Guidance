from flask import Blueprint, jsonify, request, render_template
import datetime, json
from ..db import connect, log
from ..projects_helpers import load as load_project
from ..gpio import red_led, pedal
from ..config import DEVICE_ID

bp = Blueprint("kiosk", __name__)

@bp.route("/")
def screen():
    return render_template("index.html")

@bp.post("/api/claim")
def claim():
    with connect() as c:
        cur=c.execute("""UPDATE runs
                         SET status='active', ts_started=?, device=?
                         WHERE session_id = (
                            SELECT session_id FROM runs
                             WHERE status='pending'
                             ORDER BY ts_created LIMIT 1
                         )
                         RETURNING *""",
                       (datetime.datetime.now().isoformat(timespec="seconds"),
                        DEVICE_ID))
        row=cur.fetchone()
    if row is None:
        return jsonify(status="none")
    cfg=load_project(row["project"]) or {"sequence":[]}
    return jsonify(status="claimed",
                   session=dict(row), sequence=cfg["sequence"])

@bp.post("/api/progress")
def progress():
    data=request.json
    sid=data["session_id"]; act=data["action"]
    if act=="next":
        red_led.toggle(); log(f"next_pressed::{sid}")
        return jsonify(status="ok")
    with connect() as c:
        if act=="finish":
            c.execute("UPDATE runs SET status='finished', ts_finished=? WHERE session_id=?",
                      (datetime.datetime.now().isoformat(timespec="seconds"), sid))
            log(f"session_end::{json.dumps({'session_id':sid})}")
        elif act=="abort":
            c.execute("""UPDATE runs SET status='aborted',
                         ts_finished=?, interrupted_at=?
                         WHERE session_id=?""",
                      (datetime.datetime.now().isoformat(timespec="seconds"),
                       data.get("step"), sid))
            log(f"session_abort::{json.dumps({'session_id':sid,'step':data.get('step')})}")
    return jsonify(status="ok")

@bp.get("/pedal")
def pedal_state():
    return jsonify(pressed=bool(getattr(pedal,"is_active",False)))
