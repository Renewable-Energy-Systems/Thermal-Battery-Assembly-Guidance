from flask import Blueprint, render_template, redirect, send_file
from ..logbook import overview_rows, timeline, export_overview, export_detail

bp = Blueprint("logsBP", __name__)

@bp.get("/logs")
def overview():
    return render_template("logs_overview.html", rows=overview_rows())

@bp.get("/logs/<sid>")
def detail(sid):
    data=timeline(sid)
    if not data: return f"No logs for {sid}",404
    return render_template("log_detail.html", events=data, sid=sid)

@bp.get("/logs/export")
def xl_overview():
    return send_file(export_overview(), as_attachment=True,
                     download_name="sessions.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@bp.get("/logs/<sid>/export")
def xl_detail(sid):
    buf=export_detail(sid)
    return send_file(buf, as_attachment=True,
                     download_name=f"{sid}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
