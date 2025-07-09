"""
Project-library (process-recipe) management UI
──────────────────────────────────────────────
* List, create, edit, delete projects
* Serves project images to the kiosk
*
* Relies exclusively on **tbag.helpers.projects** for filesystem I/O.
"""

from __future__ import annotations
from flask import (
    Blueprint, render_template, request, redirect,
    send_from_directory, jsonify, abort
)
import werkzeug.datastructures as wz
import uuid, pathlib

# ─── Canonical helper layer ──────────────────────────────────────────────
#   ☞ THIS replaces the old “projects_helpers” import everywhere.
from ..helpers.projects import (
    projects_list, load_config, save_config, new_project_slug, PROJECTS
)

from ..components_helpers import list_components          # component library

bp = Blueprint("projects", __name__)                      # /projects…

# ──────────────────────────────────────────────────────────────────────────
# 1) JSON feed – used by Admin screen (polls every few seconds)
# ------------------------------------------------------------------------
@bp.get("/projects/json")
def projects_json():
    data = [
        {"id": p.name, "name": load_config(p.name)["name"]}
        for p in projects_list() if load_config(p.name)
    ]
    return jsonify(data)


# 2) HTML list ------------------------------------------------------------
@bp.get("/projects")
def list_projects():
    projs = [
        {"id": p.name, "name": load_config(p.name)["name"]}
        for p in projects_list() if load_config(p.name)
    ]
    return render_template("project_list.html", projects=projs)


# 3) Create new -----------------------------------------------------------
@bp.route("/projects/new", methods=("GET", "POST"))
def new():
    if request.method == "POST":
        name = request.form["proj_name"].strip()
        # uniqueness check (case-insensitive)
        for p in projects_list():
            cfg = load_config(p.name)
            if cfg and cfg["name"].lower() == name.lower():
                return render_template(
                    "project_new.html",
                    error=f'Project “{name}” already exists.'
                )

        pid = new_project_slug(name)
        save_config(pid, {"name": name, "sequence": []})
        return redirect(f"/projects/{pid}/edit")

    # GET
    return render_template("project_new.html")


# 4) Edit existing --------------------------------------------------------
@bp.route("/projects/<pid>/edit", methods=("GET", "POST"))
def edit(pid: str):
    cfg = load_config(pid)
    if not cfg:
        abort(404, f"Project {pid!r} not found")

    if request.method == "POST":
        seq, idx = [], 0
        while True:
            comp_id = request.form.get(f"comp_{idx}")
            if comp_id is None:                # ran out of rows
                break

            label = request.form.get(f"label_{idx}", "").strip()
            if comp_id:                        # skip empty
                seq.append({"comp": comp_id, "label": label})
            idx += 1

        cfg["sequence"] = seq
        save_config(pid, cfg)
        return redirect("/projects")

    # GET – render editor
    components = list_components()             # dropdown options
    return render_template(
        "project_edit.html",
        project   = cfg,
        sequence  = cfg["sequence"],
        components= components
    )


# 5) Serve project images --------------------------------------------------
@bp.get("/proj_assets/<pid>/<path:fname>")
def asset(pid: str, fname: str):
    return send_from_directory(PROJECTS / pid / "images", fname)
