# tbag/blueprints/admin.py
from flask import Blueprint, render_template, redirect, request, abort
import sqlite3, datetime, uuid, json
from ..config import DB_FILE
from ..helpers.projects import projects_list, load_config

bp = Blueprint("admin", __name__, url_prefix="/admin")

# ──────────────────────────────────────────────────────────────────────────
@bp.route("/")
def dashboard():
    return render_template("admin_dashboard.html")

# ───────── Session queue screen ───────────────────────────────────────────
@bp.route("/sessions")
def sessions():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row          # ✅ use module attribute
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY ts_created DESC"
        ).fetchall()

    projs = [{"id": p.name, "name": load_config(p.name)["name"]}
             for p in projects_list()]
    return render_template("admin_sessions.html", rows=rows, projects=projs)

# ───────── Create new session ─────────────────────────────────────────────
@bp.route("/sessions/new", methods=["POST"])
def sessions_new():
    sid = uuid.uuid4().hex[:8]
    payload = dict(
        session_id=sid,
        project   =request.form["project"],
        stack_id  =request.form["stack_id"],
        operator  =request.form["operator"],
        ts_created=datetime.datetime.now().isoformat(timespec="seconds"),
        status    ="pending",
    )
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO runs(session_id,project,stack_id,operator,
                             ts_created,status)
            VALUES(:session_id,:project,:stack_id,:operator,:ts_created,:status)
        """, payload)
    return redirect("/admin/sessions")

# ───────── Delete (only if still pending) ────────────────────────────────
@bp.route("/sessions/<sid>/delete", methods=["POST"])
def sessions_delete(sid):
    with sqlite3.connect(DB_FILE) as conn:
        deleted = conn.execute(
            "DELETE FROM runs WHERE session_id=? AND status='pending'", (sid,)
        ).rowcount
    if deleted == 0:
        abort(400, "Cannot delete — session already active or finished.")
    return redirect("/admin/sessions")
