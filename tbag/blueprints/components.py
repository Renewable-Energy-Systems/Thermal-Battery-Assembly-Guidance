"""
Blueprint for managing *Components* that can be reused across projects.
"""

from flask import Blueprint, render_template, request, redirect, send_from_directory
import uuid, pathlib
import werkzeug.datastructures as wz

from ..helpers.components import (
    COMPONENTS,
    components_list,
    load_component,
    save_component,
    new_component_slug,
)

bp = Blueprint("componentsBP", __name__)


# ── list ────────────────────────────────────────────────────────────
@bp.get("/components")
def list_components():
    comps = [
        {"id": p.name, "name": load_component(p.name)["name"]}
        for p in components_list()
    ]
    return render_template("component_list.html", components=comps)


# ── create ──────────────────────────────────────────────────────────
@bp.route("/components/new", methods=["GET", "POST"])
def new_component():
    if request.method == "POST":
        name = request.form["comp_name"].strip()
        if any(load_component(p.name)["name"].lower() == name.lower()
               for p in components_list()):
            return render_template(
                "component_new.html",
                error=f'Component “{name}” already exists.'
            )

        cid = new_component_slug(name)
        # Handle optional image
        img_name = None
        fs: wz.FileStorage = request.files.get("comp_img")  # type: ignore
        if fs and fs.filename:
            img_name = f"preview_{uuid.uuid4().hex[:6]}{pathlib.Path(fs.filename).suffix}"
            (COMPONENTS / cid / "images").mkdir(parents=True, exist_ok=True)
            fs.save(COMPONENTS / cid / "images" / img_name)

        save_component(cid, {"name": name, "image": img_name})
        return redirect("/components")

    return render_template("component_new.html")


# ── edit ────────────────────────────────────────────────────────────
@bp.route("/components/<cid>/edit", methods=["GET", "POST"])
def edit_component(cid):
    cfg = load_component(cid) or {"name": cid, "image": None}
    if request.method == "POST":
        cfg["name"] = request.form["comp_name"].strip()

        # replace image if a new file was chosen
        fs: wz.FileStorage = request.files.get("comp_img")  # type: ignore
        if fs and fs.filename:
            img_name = f"preview_{uuid.uuid4().hex[:6]}{pathlib.Path(fs.filename).suffix}"
            (COMPONENTS / cid / "images").mkdir(parents=True, exist_ok=True)
            fs.save(COMPONENTS / cid / "images" / img_name)
            cfg["image"] = img_name

        save_component(cid, cfg)
        return redirect("/components")

    return render_template("component_edit.html", comp=cfg, cid=cid)


# ── delete ──────────────────────────────────────────────────────────
@bp.post("/components/<cid>/delete")
def delete_component(cid):
    # Optional safety: refuse delete if any project references this component
    import shutil
    shutil.rmtree(COMPONENTS / cid, ignore_errors=True)
    return redirect("/components")


# ── asset helper ────────────────────────────────────────────────────
@bp.get("/comp_assets/<cid>/<path:fname>")
def comp_asset(cid, fname):
    return send_from_directory(COMPONENTS / cid / "images", fname)
