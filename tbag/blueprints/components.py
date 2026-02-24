"""
Blueprint for managing *Components* that can be reused across projects.
"""

from __future__ import annotations

import uuid
import pathlib
from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    redirect,
    send_from_directory,
)
import werkzeug.datastructures as wz

from ..helpers.components import (
    COMPONENTS,
    ALLOWED_GPIO_PINS,
    GPIO_LABELS,          # ← labels “L1…L23”
    components_list,
    load_component,
    save_component,
    new_component_slug,
)

bp = Blueprint("componentsBP", __name__)

# ───────────────────────── list ─────────────────────────────────
@bp.get("/components")
def list_components_route():
    comps = []
    for p in components_list():
        cfg = load_component(p.name)
        if not cfg:
            continue
        comps.append({
            "id": p.name,
            "name": cfg["name"],
            "image": cfg.get("image"),
            "default_thickness": cfg.get("default_thickness", 0.0),
        })
    return render_template("component_list.html", components=comps)


# ── tiny JSON helper (used by kiosk) ────────────────────────────
@bp.get("/components/json")
def components_json():
    """Return id, name and optional preview image for every component."""
    return jsonify(
        [
            {
                "id": p.name,
                "name": cfg["name"],
                "image": cfg.get("image"),  # may be None
                "default_thickness": cfg.get("default_thickness", 0.0),
            }
            for p in components_list()
            if (cfg := load_component(p.name))              # cfg is not None here
        ]
    )


# ───────────────────────── create ───────────────────────────────
@bp.route("/components/new", methods=["GET", "POST"])
def new_component():
    if request.method == "POST":
        name = request.form["comp_name"].strip()
        default_thickness = float(request.form.get("default_thickness", 0.0))

        # duplicate-name check (case-insensitive, None-safe)
        duplicate = any(
            (cfg := load_component(p.name))
            and cfg.get("name", "").lower() == name.lower()
            for p in components_list()
        )
        if duplicate:
            return render_template(
                "component_new.html",
                error=f'Component “{name}” already exists.',
            )

        cid = new_component_slug(name)

        # optional preview image
        img_name: str | None = None
        fs: wz.FileStorage = request.files.get("comp_img")  # type: ignore
        if fs and fs.filename:
            img_name = (
                f"preview_{uuid.uuid4().hex[:6]}"
                f"{pathlib.Path(fs.filename).suffix}"
            )
            (COMPONENTS / cid / "images").mkdir(parents=True, exist_ok=True)
            fs.save(COMPONENTS / cid / "images" / img_name)

            fs.save(COMPONENTS / cid / "images" / img_name)

        save_component(cid, {
            "name": name,
            "image": img_name,
            "default_thickness": default_thickness,
        })
        return redirect("/components")

    # GET – blank form
    return render_template("component_new.html")


# ───────────────────────── edit ────────────────────────────────
@bp.route("/components/<cid>/edit", methods=["GET", "POST"])
def edit_component(cid):
    cfg = load_component(cid) or {
        "name": cid,
        "image": None,
        "default_thickness": 0.0,
    }

    if request.method == "POST":
        cfg["name"] = request.form["comp_name"].strip()
        cfg["default_thickness"] = float(request.form.get("default_thickness", 0.0))

        # replace image if a new file was chosen
        fs: wz.FileStorage = request.files.get("comp_img")  # type: ignore
        if fs and fs.filename:
            img_name = (
                f"preview_{uuid.uuid4().hex[:6]}"
                f"{pathlib.Path(fs.filename).suffix}"
            )
            (COMPONENTS / cid / "images").mkdir(parents=True, exist_ok=True)
            fs.save(COMPONENTS / cid / "images" / img_name)
            cfg["image"] = img_name

        save_component(cid, cfg)
        return redirect("/components")

    # GET – pre-filled form
    return render_template(
        "component_edit.html",
        comp=cfg,
        cid=cid,
    )


# ───────────────────────── delete ───────────────────────────────
@bp.post("/components/<cid>/delete")
def delete_component(cid):
    """Remove a component folder (no dependency checks)."""
    import shutil

    shutil.rmtree(COMPONENTS / cid, ignore_errors=True)
    return redirect("/components")


# ───────────────────────── asset helper ─────────────────────────
@bp.get("/comp_assets/<cid>/<path:fname>")
def comp_asset(cid, fname):
    return send_from_directory(COMPONENTS / cid / "images", fname)
