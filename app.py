#!/usr/bin/env python3
"""
Offline-first Flask app for Thermal-Battery Assembly Guidance
──────────────────────────────────────────────────────────────
Key routes
/select              → choose project / stack / operator
/start   (POST)      → begin a run, store session, log start
/        (GET)       → guidance screen (plays sequence)
/next    (POST)      → toggle LED, log step advance
/finish  (POST)      → log session end, clear session, reply OK
/admin               → admin dashboard
/projects[...]       → project CRUD
/logs                → 500 most-recent events (for admins)
"""

# ── std-lib ────────────────────────────────────────────────────────────────
import os, sys, json, uuid, datetime, sqlite3, pathlib
from typing import List, Dict, Optional
import werkzeug.datastructures

# ── Flask ──────────────────────────────────────────────────────────────────
from flask import (
    Flask, render_template, request, redirect, session,
    jsonify, send_from_directory
)

# ── GPIOZero safe import (mock on dev PCs) ────────────────────────────────
try:
    from gpiozero import LED, Button, Device

    if not (sys.platform.startswith("linux") and os.path.exists("/proc/cpuinfo")):
        from gpiozero.pins.mock import MockFactory

        Device.pin_factory = MockFactory()          # desktop → mock pins
except ImportError:
    class _Dummy:                                  # no-op stand-in
        def __getattr__(self, *_): return lambda *a, **k: None
        is_active = False
    LED = Button = _Dummy  # type: ignore

# ── paths & Flask init ─────────────────────────────────────────────────────
BASE      = pathlib.Path(__file__).parent
PROJECTS  = BASE / "projects"; PROJECTS.mkdir(exist_ok=True)
DB_FILE   = BASE / "events.db"

app = Flask(__name__, template_folder=str(BASE / "templates"))
app.secret_key = "change-me"              # ⚠ set a real secret in prod
app.config.update(TEMPLATES_AUTO_RELOAD=True, SEND_FILE_MAX_AGE_DEFAULT=0)
app.jinja_env.auto_reload = True

red_led, pedal = LED(17), Button(27)      # BCM pins

# ── SQLite helpers ─────────────────────────────────────────────────────────
def init_db() -> None:
    with sqlite3.connect(DB_FILE) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                ts    TEXT,
                event TEXT
            )""")
def log(event: str) -> None:
    with sqlite3.connect(DB_FILE) as c:
        c.execute(
            "INSERT INTO events VALUES (?,?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), event),
        )

init_db()

# ── project helpers ────────────────────────────────────────────────────────
def projects_list() -> List[pathlib.Path]:
    return sorted((d for d in PROJECTS.iterdir() if d.is_dir()),
                  key=lambda p: p.name.lower())

def load_config(pid: str) -> Optional[Dict]:
    cfg = PROJECTS / pid / "config.json"
    return json.load(cfg.open()) if cfg.exists() else None

def save_config(pid: str, data: Dict) -> None:
    d = PROJECTS / pid
    (d / "images").mkdir(parents=True, exist_ok=True)
    with (d / "config.json").open("w") as f:
        json.dump(data, f, indent=2)

# ── runtime routes ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "run" not in session:
        return redirect("/select")

    pid = session["run"]["project"]
    cfg = load_config(pid) or {"sequence": []}
    return render_template(
        "index.html",
        sequence=cfg["sequence"],
        meta=session["run"],
    )

@app.route("/select")
def select_project():
    projs = [{"id": d.name, "name": load_config(d.name)["name"]}
             for d in projects_list()]
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

# ── finish & abort ──────────────────────────────────────────────────────────
@app.post("/finish")
def finish_session():
    if "run" in session:
        data = session["run"]
        log(f"session_end::{json.dumps(data)}")
        session["last"] = data          # keep for summary
        session.pop("run", None)
    return jsonify(status="finished")

@app.post("/abort")
def abort_session():
    if "run" in session:
        step_idx = request.json.get("step", -1)
        payload  = {**session["run"], "interrupted_at": step_idx}
        log(f"session_abort::{json.dumps(payload)}")
        session["last"] = payload
        session.pop("run", None)
    return jsonify(status="aborted")

# ── summary ─────────────────────────────────────────────────────────────────
@app.get("/summary")
def summary():
    if "last" not in session:
        return redirect("/select")
    details = session.pop("last")
    return render_template("summary.html", info=details)


# ── pedal status ───────────────────────────────────────────────────────────
@app.get("/pedal")
def pedal_status():
    return jsonify(pressed=bool(getattr(pedal, "is_active", False)))

# ── admin & project CRUD ────────────────────────────────────────────────────
@app.get("/admin")
def admin_dash():
    return render_template("admin_dashboard.html")

@app.get("/projects")
def list_projects():
    projs = [{"id": d.name, "name": load_config(d.name)["name"]}
             for d in projects_list()]
    return render_template("project_list.html", projects=projs)

@app.route("/projects/new", methods=["GET", "POST"])
def new_project():
    if request.method == "POST":
        name = request.form["proj_name"].strip()
        # duplicate check
        clash = [p for p in projects_list()
                 if load_config(p.name)["name"].lower() == name.lower()]
        if clash:
            err = f'Project "{name}" already exists. Please EDIT or DELETE it.'
            return render_template("project_new.html", error=err)

        pid = name.replace(" ", "_").lower()[:40] or uuid.uuid4().hex[:6]
        save_config(pid, {"name": name, "sequence": []})
        return redirect(f"/projects/{pid}/edit")

    return render_template("project_new.html", error=None)

@app.route("/projects/<pid>/edit", methods=["GET", "POST"])
def edit_project(pid):
    cfg = load_config(pid)
    if not cfg:
        return "Project not found", 404

    if request.method == "POST":
        seq: List[Dict] = []
        idx = 0
        while True:
            lbl = request.form.get(f"label_{idx}")
            if lbl is None:
                break

            img_fs: werkzeug.datastructures.FileStorage | None = \
                request.files.get(f"img_{idx}")
            img_name = cfg["sequence"][idx]["img"] \
                if idx < len(cfg["sequence"]) else None

            if img_fs and img_fs.filename:
                img_name = (
                    f"step{idx}_{uuid.uuid4().hex[:6]}"
                    f"{pathlib.Path(img_fs.filename).suffix}"
                )
                img_fs.save(PROJECTS / pid / "images" / img_name)

            seq.append({"label": lbl, "img": img_name})
            idx += 1

        cfg["sequence"] = seq
        save_config(pid, cfg)
        return redirect("/projects")

    return render_template("project_edit.html",
                           project=cfg, sequence=cfg["sequence"])

@app.get("/proj_assets/<pid>/<path:fname>")
def proj_assets(pid, fname):
    return send_from_directory(PROJECTS / pid / "images", fname)

# ── logs viewer ─────────────────────────────────────────────────────────────
@app.get("/logs")
def view_logs():
    rows: List[Dict] = []
    with sqlite3.connect(DB_FILE) as c:
        for ts, ev in c.execute(
            "SELECT ts,event FROM events ORDER BY ts DESC LIMIT 500"
        ):
            rows.append({"ts": ts, "event": ev})
    return render_template("logs.html", rows=rows)

# ── run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=8000, debug=True, use_reloader=True)
