# ─── tbag/blueprints/admin.py ─────────────────────────────────────────────
from __future__ import annotations
import sqlite3, datetime, uuid
from flask import Blueprint, render_template, redirect, request, abort, jsonify

from ..config import DB_FILE
from ..helpers.projects import projects_list, load_config

bp = Blueprint("admin", __name__, url_prefix="/admin")

# ──────────────────────────────────────────────────────────────────────────
@bp.route("/")
def dashboard():
    return render_template("admin_dashboard.html")

# ─────────────── session table (HTML) ─────────────────────────────────────
@bp.get("/sessions")
def sessions():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row          # <— correct attr
        rows = c.execute(
            "SELECT * FROM runs ORDER BY ts_created DESC"
        ).fetchall()

    projs = [{"id": p.name, "name": load_config(p.name)["name"]}
             for p in projects_list()]
    return render_template("admin_sessions.html",
                           rows=rows, projects=projs)

# ─────────────── live JSON feed (AJAX) ────────────────────────────────────
@bp.get("/sessions/json")
def sessions_json():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM runs ORDER BY ts_created DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])

# ─────────────── create new pending run ───────────────────────────────────
@bp.post("/sessions/new")
def sessions_new():
    payload = dict(
        session_id = uuid.uuid4().hex[:8],
        project    = request.form["project"],
        stack_id   = request.form["stack_id"],
        operator   = request.form["operator"],
        ts_created = datetime.datetime.now().isoformat(timespec="seconds"),
        status     = "pending"
    )
    with sqlite3.connect(DB_FILE) as c:
        c.execute("""INSERT INTO runs(session_id,project,stack_id,operator,
                                      ts_created,status)
                     VALUES(:session_id,:project,:stack_id,:operator,
                            :ts_created,:status)""", payload)
    return redirect("/admin/sessions")

# ─────────────── delete (only while still pending) ────────────────────────
@bp.post("/sessions/<sid>/delete")
def sessions_delete(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        deleted = c.execute(
            "DELETE FROM runs WHERE session_id=? AND status='pending'", (sid,)
        ).rowcount
    if not deleted:
        abort(400, "Cannot delete — session already active or finished.")
    return redirect("/admin/sessions")
