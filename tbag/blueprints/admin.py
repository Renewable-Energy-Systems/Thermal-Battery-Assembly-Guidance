"""
Admin views – dashboard, session queue, device list (fixed).
"""
from __future__ import annotations

import datetime
import sqlite3
import uuid

from flask import Blueprint, abort, jsonify, redirect, render_template, request

from ..config import DB_FILE
from ..helpers.projects import load_config, projects_list
from ..helpers.settings import load_settings, save_settings

bp = Blueprint("admin", __name__, url_prefix="/admin")

# ───────── settings ─────────────────
@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        # Payload structure: P1_x, P1_y, ...
        # We need to reconstruct the JSON
        current = load_settings()
        tps = current.get("teachpoints", {})
        
        for key in tps.keys():
            # key = "P1", "P2", ...
            try:
                tps[key]["x"] = float(request.form.get(f"{key}_x", 0.0))
                tps[key]["y"] = float(request.form.get(f"{key}_y", 0.0))
                tps[key]["z"] = float(request.form.get(f"{key}_z", 0.0))
                tps[key]["r"] = float(request.form.get(f"{key}_r", 0.0))
            except ValueError:
                pass # keep old value or 0.0
        
        current["teachpoints"] = tps
        save_settings(current)
        return redirect("/admin/settings")

    data = load_settings()
    return render_template("admin_settings.html", settings=data)


# ───────── dashboard (home) ─────────
@bp.get("/")
def dashboard():
    return render_template("admin_dashboard.html")

# ───────── sessions list/page ───────
@bp.get("/sessions")
def sessions():
    return render_template("admin_sessions.html")

@bp.get("/sessions/json")
def sessions_json():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM runs ORDER BY ts_created DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@bp.post("/sessions/new")
def sessions_new():
    payload = dict(
        session_id=uuid.uuid4().hex[:8],
        project=request.form["project"],
        stack_id=request.form["stack_id"],
        operator=request.form["operator"],
        ts_created=datetime.datetime.now().isoformat(timespec="seconds"),
        status="pending",
        device=request.form.get("device") or None,
    )
    with sqlite3.connect(DB_FILE) as c:
        c.execute(
            """INSERT INTO runs(session_id, project, stack_id, operator,
                                ts_created, status, device)
               VALUES(:session_id, :project, :stack_id, :operator,
                      :ts_created, :status, :device)""",
            payload,
        )
    return redirect("/admin/sessions")

@bp.post("/sessions/<sid>/delete")
def sessions_delete(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        deleted = c.execute(
            "DELETE FROM runs WHERE session_id=? AND status='pending'", (sid,)
        ).rowcount
    if not deleted:
        abort(400, "Cannot delete — session already active or finished.")
    return redirect("/admin/sessions")

# ───────── fixed device list ───────
@bp.get("/devices/json")
def devices_json():
    """Return the two hard-coded device choices."""
    return jsonify(["any", "local-pi"])
