"""
Logs / XLS export endpoints
───────────────────────────
• /logs              – session overview table
• /logs/<sid>        – timeline of a single session
• /logs/export       – overview → Excel
• /logs/<sid>/export – timeline  → Excel
"""
from flask import Blueprint, render_template, send_file, abort
from ..logbook import overview_rows, timeline, export_overview, export_detail

bp = Blueprint("logsBP", __name__)

# ── overview – one row per session ────────────────────────────────────────
@bp.get("/logs")
def overview():
    return render_template("logs_overview.html", rows=overview_rows())

# ── per-session timeline ──────────────────────────────────────────────────
@bp.get("/logs/<sid>")
def detail(sid):
    evs = timeline(sid)
    if not evs:
        abort(404, f"no events for session {sid}")
    return render_template("log_detail.html", events=evs, sid=sid)

# ── export helpers ────────────────────────────────────────────────────────
@bp.get("/logs/export")
def xl_overview():
    return send_file(export_overview(), as_attachment=True,
                     download_name="sessions.xlsx",
                     mimetype=("application/"
                               "vnd.openxmlformats-officedocument."
                               "spreadsheetml.sheet"))

@bp.get("/logs/<sid>/export")
def xl_detail(sid):
    return send_file(export_detail(sid), as_attachment=True,
                     download_name=f"{sid}.xlsx",
                     mimetype=("application/"
                               "vnd.openxmlformats-officedocument."
                               "spreadsheetml.sheet"))
