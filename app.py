#!/usr/bin/env python3
"""
Offline-first Flask app for Thermal-Battery Assembly Guidance
──────────────────────────────────────────────────────────────
Admin     → /admin
Run flow  → /select → /      (Next Step / Finish / Abort)
Projects  → /projects … CRUD, images per step
Logs      → /logs            (overview)      +  /logs/export
             /logs/<sid>     (timeline)      +  /logs/<sid>/export
"""

# ── std-lib ────────────────────────────────────────────────────────────────
import os, sys, json, uuid, datetime, sqlite3, pathlib, hashlib, io
from typing import List, Dict, Optional

# ── third-party ────────────────────────────────────────────────────────────
from flask import (
    Flask, render_template, request, redirect, session,
    jsonify, send_from_directory, send_file
)
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
import werkzeug.datastructures

# ── GPIOZero: force mock factory (dev mode) ────────────────────────────────
try:
    from gpiozero import LED, Button, Device
    from gpiozero.pins.mock import MockFactory
    Device.pin_factory = MockFactory()  # ← force mock GPIO for dev/testing
except ImportError:
    class _Dummy:
        def __getattr__(self, *_): return lambda *a, **k: None
        is_active = False
    LED = Button = _Dummy  # type: ignore

# ── paths & Flask init ─────────────────────────────────────────────────────
BASE      = pathlib.Path(__file__).parent
PROJECTS  = BASE / "projects"; PROJECTS.mkdir(exist_ok=True)
DB_FILE   = BASE / "events.db"

app = Flask(__name__, template_folder=str(BASE / "templates"))
app.secret_key = "change-me"        # ⚠ replace for production
app.config.update(TEMPLATES_AUTO_RELOAD=True, SEND_FILE_MAX_AGE_DEFAULT=0)
app.jinja_env.auto_reload = True

red_led, pedal = LED(17), Button(27)        # BCM pins

# ── SQLite helpers ─────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_FILE) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS events(
                       ts    TEXT,
                       event TEXT
                     )""")
def log(event: str):
    with sqlite3.connect(DB_FILE) as c:
        c.execute("INSERT INTO events VALUES(?,?)",
                  (datetime.datetime.now().isoformat(timespec="seconds"), event))
init_db()

# ── project helpers ────────────────────────────────────────────────────────
def projects_list() -> List[pathlib.Path]:
    return sorted((d for d in PROJECTS.iterdir() if d.is_dir()),
                  key=lambda p: p.name.lower())

def load_config(pid: str) -> Optional[Dict]:
    cfg = PROJECTS / pid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None

def save_config(pid: str, data: Dict):
    d = PROJECTS / pid
    (d / "images").mkdir(parents=True, exist_ok=True)
    with (d / "config.json").open("w") as f:
        json.dump(data, f, indent=2)

# ── logs data helpers (shared by routes + exporter) ────────────────────────
def _hue_for_proj(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest()[:2], 16) * 360 // 255

def logs_overview_data() -> List[Dict]:
    rows = []
    with sqlite3.connect(DB_FILE) as c:
        for ts, ev in c.execute(
            "SELECT ts,event FROM events "
            "WHERE event LIKE 'session_%' ORDER BY ts DESC"):
            kind, payload = ev.split("::", 1)
            if kind == "session_start":
                continue
            d = json.loads(payload)
            rows.append({
                "ts": ts, "kind": kind.replace("session_", ""),
                "project": d["project"], "stack_id": d["stack_id"],
                "operator": d["operator"], "session_id": d["session_id"],
                "step": d.get("interrupted_at"),
                "hue": _hue_for_proj(d["project"]),
            })
    return rows

def log_detail_data(sid: str) -> List[Dict]:
    events = []
    with sqlite3.connect(DB_FILE) as c:
        for ts, raw in c.execute(
                "SELECT ts,event FROM events WHERE event LIKE ? ORDER BY ts",
                (f"%{sid}%",)):
            if "::" in raw:
                k, p = raw.split("::", 1)
                p = json.loads(p)
            else:
                k, p = raw, {}
            events.append({"ts": ts, "kind": k, "payload": p})
    return events

# ── Excel helper ───────────────────────────────────────────────────────────
def _list_to_sheet(wb: Workbook, title: str, header: list, rows: list):
    ws = wb.create_sheet(title)
    ws.append(header)
    for r in rows:
        ws.append(r)
    for col in range(1, len(header)+1):
        ws.column_dimensions[get_column_letter(col)].width = 16

# ── runtime routes ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "run" not in session:
        return redirect("/select")
    pid = session["run"]["project"]
    cfg = load_config(pid) or {"sequence": []}
    return render_template("index.html",
                           sequence=cfg["sequence"], meta=session["run"])

@app.route("/select")
def select_project():
    projs = [{"id": p.name, "name": load_config(p.name)["name"]}
             for p in projects_list()]
    return render_template("project_select.html", projects=projs)

@app.post("/start")
def start_session():
    data = {k: request.form[k] for k in ("project", "stack_id", "operator")}
    data.update(session_id=uuid.uuid4().hex[:8],
                timestamp=request.form["timestamp"])
    session["run"] = data
    log(f"session_start::{json.dumps(data)}")
    return redirect("/")

@app.post("/next")
def next_step():
    red_led.toggle()
    log("next_pressed")
    return jsonify(status="ok")

@app.post("/finish")
def finish_session():
    if "run" in session:
        data = session["run"]
        log(f"session_end::{json.dumps(data)}")
        session["last"] = data
        session.pop("run", None)
    return jsonify(status="finished")

@app.post("/abort")
def abort_session():
    if "run" in session:
        step = request.json.get("step", -1)
        payload = {**session["run"], "interrupted_at": step}
        log(f"session_abort::{json.dumps(payload)}")
        session["last"] = payload
        session.pop("run", None)
    return jsonify(status="aborted")

@app.get("/summary")
def summary():
    if "last" not in session:
        return redirect("/select")
    return render_template("summary.html", info=session.pop("last"))

@app.get("/pedal")
def pedal_status():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))

# ── admin & projects ───────────────────────────────────────────────────────
@app.get("/admin")
def admin_dash():
    return render_template("admin_dashboard.html")

@app.get("/projects")
def list_projects():
    projs = [{"id": p.name, "name": load_config(p.name)["name"]}
             for p in projects_list()]
    return render_template("project_list.html", projects=projs)

@app.route("/projects/new", methods=["GET", "POST"])
def new_project():
    if request.method == "POST":
        name = request.form["proj_name"].strip()
        if any(load_config(p.name)["name"].lower() == name.lower()
               for p in projects_list()):
            err = f'Project "{name}" already exists.'
            return render_template("project_new.html", error=err)
        pid = name.replace(" ", "_").lower()[:40] or uuid.uuid4().hex[:6]
        save_config(pid, {"name": name, "sequence": []})
        return redirect(f"/projects/{pid}/edit")
    return render_template("project_new.html", error=None)

@app.route("/projects/<pid>/edit", methods=["GET", "POST"])
def edit_project(pid):
    cfg = load_config(pid) or {"name": pid, "sequence": []}
    if request.method == "POST":
        seq, idx = [], 0
        while True:
            lbl = request.form.get(f"label_{idx}")
            if lbl is None:
                break
            img = cfg["sequence"][idx]["img"] if idx < len(cfg["sequence"]) else None
            fs: werkzeug.datastructures.FileStorage = request.files.get(f"img_{idx}")  # type: ignore
            if fs and fs.filename:
                img = f"step{idx}_{uuid.uuid4().hex[:6]}{pathlib.Path(fs.filename).suffix}"
                fs.save(PROJECTS / pid / "images" / img)
            seq.append({"label": lbl, "img": img})
            idx += 1
        cfg["sequence"] = seq
        save_config(pid, cfg)
        return redirect("/projects")
    return render_template("project_edit.html", project=cfg, sequence=cfg["sequence"])

@app.get("/proj_assets/<pid>/<path:fname>")
def proj_assets(pid, fname):
    return send_from_directory(PROJECTS / pid / "images", fname)

# ── logs overview / detail + export ────────────────────────────────────────
@app.get("/logs")
def logs_overview():
    return render_template("logs_overview.html", rows=logs_overview_data())

@app.get("/logs/<sid>")
def log_detail(sid):
    evs = log_detail_data(sid)
    if not evs:
        return f"No logs for session {sid}", 404
    return render_template("log_detail.html", events=evs, sid=sid)

# Excel exports
@app.get("/logs/export")
def export_overview():
    wb = Workbook(); wb.remove(wb.active)
    data = logs_overview_data()
    _list_to_sheet(
        wb, "sessions",
        ["Started","Project","Stack","Operator","Status","Step","Session ID"],
        [[r["ts"], r["project"], r["stack_id"], r["operator"],
          r["kind"], (r["step"]+1) if r["step"] is not None else "", r["session_id"]]
         for r in data]
    )
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="sessions.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.get("/logs/<sid>/export")
def export_detail(sid):
    evs = log_detail_data(sid)
    if not evs:
        return redirect("/logs")
    wb = Workbook(); wb.remove(wb.active)
    _list_to_sheet(
        wb, "timeline",
        ["Time","Event","Payload"],
        [[e["ts"], e["kind"], json.dumps(e["payload"], separators=(',', ':'))] for e in evs]
    )
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"{sid}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── run dev server ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=8000, debug=True, use_reloader=True)
