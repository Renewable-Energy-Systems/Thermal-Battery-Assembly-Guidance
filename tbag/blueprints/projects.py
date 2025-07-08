"""
Blueprint: /projects CRUD
─────────────────────────
• Keeps every project **inside <tbag>/projects/** (defined in helpers.projects)
• Provides create / list / edit / delete endpoints
"""

from __future__ import annotations
import uuid, shutil
import werkzeug.datastructures as wds
from flask import (
    Blueprint, render_template, request, redirect,
    send_from_directory, abort,
)

# unified helper set (path + utils all in one place)
from ..helpers.projects import (
    projects_list,
    load_config,
    save_config,
    new_project_slug,
    PROJECTS,               # <tbag>/projects  Path object
)

bp = Blueprint("projBP", __name__)

# ─────────────────────────────── views ────────────────────────────────────
@bp.get("/projects")
def list_projects():
    """Table of all projects."""
    projs = [
        {
            "id": p.name,
            "name": (load_config(p.name) or {}).get("name", p.name),
        }
        for p in projects_list()
    ]
    return render_template("project_list.html", projects=projs)


@bp.route("/projects/new", methods=["GET", "POST"])
def new_project():
    """Create a fresh project shell – redirects straight to the editor."""
    if request.method == "POST":
        # ── uniqueness check (case-insensitive) ───────────────────────────
        name = request.form["proj_name"].strip()
        if any(
            (load_config(p.name) or {}).get("name", "").lower() == name.lower()
            for p in projects_list()
        ):
            return render_template(
                "project_new.html", error=f'Project “{name}” already exists.'
            )

        pid = new_project_slug(name)
        save_config(pid, {"name": name, "sequence": []})
        return redirect(f"/projects/{pid}/edit")

    # GET
    return render_template("project_new.html")


@bp.route("/projects/<pid>/edit", methods=["GET", "POST"])
def edit_project(pid: str):
    """Add/remove/re-order steps and upload images."""
    cfg = load_config(pid) or {"name": pid, "sequence": []}

    if request.method == "POST":
        # incoming fields:  label_0 / img_0 , label_1 / img_1 …
        new_seq: list[dict] = []
        idx = 0
        while True:
            label = request.form.get(f"label_{idx}")
            if label is None:
                break  # no more rows

            # keep previous image unless a new one uploaded
            img_filename = (
                cfg["sequence"][idx]["img"] if idx < len(cfg["sequence"]) else None
            )

            fs: wds.FileStorage = request.files.get(f"img_{idx}")  # type: ignore
            if fs and fs.filename:
                img_filename = (
                    f"step{idx}_{uuid.uuid4().hex[:6]}"
                    f"{fs.filename.rsplit('.',1)[-1] and '.'+fs.filename.rsplit('.',1)[-1]}"
                )
                dest = PROJECTS / pid / "images" / img_filename
                fs.save(dest)

            new_seq.append({"label": label, "img": img_filename})
            idx += 1

        cfg["sequence"] = new_seq
        save_config(pid, cfg)
        return redirect("/projects")

    # GET
    return render_template("project_edit.html", project=cfg, sequence=cfg["sequence"])


@bp.post("/projects/<pid>/delete")
def delete_project(pid: str):
    """Hard-delete a project folder (config + images)."""
    root = PROJECTS / pid
    if not root.exists():
        abort(404, "Project not found")

    shutil.rmtree(root)
    return redirect("/projects")


@bp.get("/proj_assets/<pid>/<path:fname>")
def project_asset(pid: str, fname: str):
    """Serve step images back to the kiosk UI."""
    return send_from_directory(PROJECTS / pid / "images", fname)
