"""
Admin-side views: dashboard, session queue, live JSON feed …
"""
from __future__ import annotations

import datetime
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, List

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
)

from ..config import DB_FILE
from ..helpers.projects import load_config, projects_list  # unified helpers

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ─────────────────────────────────────────────────────────────── dashboard
@bp.get("/")
def dashboard():
    return render_template("admin_dashboard.html")


# ──────────────────────────────────────────────── session table (HTML page)
@bp.get("/sessions")
def sessions():
    # 1) read the current queue from SQLite
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM runs ORDER BY ts_created DESC"
        ).fetchall()

    # 2) build the <select> options
    projects: List[Dict[str, str]] = []
    for p in projects_list():                   # every project directory
        cfg = load_config(p.name)               # may be None if broken / empty
        if cfg:
            projects.append(
                {"id": p.name, "name": cfg.get("name", p.name)}
            )

    return render_template(
        "admin_sessions.html",
        rows=rows,
        projects=projects,
    )


# ───────────────────────────────────────────── live JSON feed for the table
@bp.get("/sessions/json")
def sessions_json():
    with sqlite3.connect(DB_FILE) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM runs ORDER BY ts_created DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ─────────────────────────────────────────────── create a pending session
@bp.post("/sessions/new")
def sessions_new():
    payload = dict(
        session_id=uuid.uuid4().hex[:8],
        project=request.form["project"],
        stack_id=request.form["stack_id"],
        operator=request.form["operator"],
        ts_created=datetime.datetime.now().isoformat(timespec="seconds"),
        status="pending",
    )

    with sqlite3.connect(DB_FILE) as c:
        c.execute(
            """INSERT INTO runs(session_id, project, stack_id, operator,
                                ts_created, status)
               VALUES(:session_id, :project, :stack_id, :operator,
                      :ts_created, :status)""",
            payload,
        )

    return redirect("/admin/sessions")


# ─────────────────────────────────────────── delete (only while pending)
@bp.post("/sessions/<sid>/delete")
def sessions_delete(sid: str):
    with sqlite3.connect(DB_FILE) as c:
        deleted = c.execute(
            "DELETE FROM runs WHERE session_id=? AND status='pending'", (sid,)
        ).rowcount

    if not deleted:
        abort(400, "Cannot delete — session already active or finished.")
    return redirect("/admin/sessions")
