from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, send_from_directory
import werkzeug.datastructures
from ..projects_helpers   import all_dirs, load, save, new_id
from ..components_helpers import list_components                       # ✅ now resolves
from ..config import PROJECTS
import pathlib, uuid

bp = Blueprint("projBP", __name__)


# ── list view ────────────────────────────────────────────────────────────
@bp.get("/projects")
def list_projects():
    projs = []
    for d in all_dirs():
        cfg = load(d.name) or {"name": d.name}             # ← safe default
        projs.append({"id": d.name, "name": cfg["name"]})
    return render_template("project_list.html", projects=projs)


# ── create new ───────────────────────────────────────────────────────────
@bp.route("/projects/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        name = request.form["proj_name"].strip()
        if any((load(p.name) or {}).get("name", "").lower() == name.lower()
               for p in all_dirs()):
            return render_template("project_new.html",
                                   error=f'Project “{name}” already exists.')
        pid = new_id(name)
        save(pid, {"name": name, "sequence": []})
        return redirect(f"/projects/{pid}/edit")

    return render_template("project_new.html")


# ── edit existing ────────────────────────────────────────────────────────
@bp.route("/projects/<pid>/edit", methods=["GET", "POST"])
def edit(pid: str):
    cfg = load(pid) or {"name": pid, "sequence": []}

    if request.method == "POST":
        seq, idx = [], 0
        while True:
            comp_id = request.form.get(f"comp_{idx}")
            if comp_id is None:                                # no more rows
                break
            label = request.form.get(f"label_{idx}", "").strip()
            if comp_id:                                        # skip blanks
                seq.append({"comp": comp_id, "label": label})
            idx += 1

        cfg["sequence"] = seq
        save(pid, cfg)
        return redirect("/projects")

    # GET – render editor
    components = list_components()                            # [{id,name,…},…]
    return render_template(
        "project_edit.html",
        project    = cfg,
        sequence   = cfg["sequence"],
        components = components
    )


# ── serve images (unchanged) ─────────────────────────────────────────────
@bp.get("/proj_assets/<pid>/<path:fname>")
def asset(pid, fname):
    return send_from_directory(PROJECTS / pid / "images", fname)
