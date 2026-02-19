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
    send_from_directory, jsonify, abort, Response
)
import werkzeug.datastructures as wz
import uuid, pathlib

# ─── Canonical helper layer ──────────────────────────────────────────────
#   ☞ THIS replaces the old “projects_helpers” import everywhere.
from ..helpers.projects import (
    projects_list, load_config, save_config, new_project_slug, PROJECTS
)

from ..helpers.components import load_component
from ..components_helpers import list_components          # component library

bp = Blueprint("projects", __name__)                      # /projects…

# ──────────────────────────────────────────────────────────────────────────
# 1) JSON feed – used by Admin screen (polls every few seconds)
# ------------------------------------------------------------------------
@bp.get("/projects/json")
def projects_json():
    data = [
        {"id": p.name, "name": load_config(p.name)["name"], "default_thickness": load_component(p.name).get("default_thickness", 0.0) if load_component(p.name) else 0.0}
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
        # Save Base Z
        try:
            cfg["base_z"] = float(request.form.get("base_z", 0.0))
        except ValueError:
            cfg["base_z"] = 0.0

        seq, idx = [], 0
        while True:
            comp_id = request.form.get(f"comp_{idx}")
            if comp_id is None:                # ran out of rows
                break

            label = request.form.get(f"label_{idx}", "").strip()
            thickness = float(request.form.get(f"thickness_{idx}", 0.0))
            teachpoint = request.form.get(f"teachpoint_{idx}", "").strip()
            
            if comp_id:                        # skip empty
                seq.append({
                    "comp": comp_id, 
                    "label": label, 
                    "thickness": thickness,
                    "teachpoint": teachpoint
                })
            idx += 1

        cfg["sequence"] = seq
        save_config(pid, cfg)
        return redirect("/projects")

    # GET – render editor
    components = list_components()             # dropdown options
    # Enrich components with default_thickness for the frontend
    for c in components:
        c_cfg = load_component(c['id'])
        c['default_thickness'] = c_cfg.get('default_thickness', 0.0) if c_cfg else 0.0

    return render_template(
        "project_edit.html",
        project   = cfg,
        sequence  = cfg["sequence"],
        components= components
    )


@bp.get("/projects/<pid>/program")
def download_program(pid: str):
    """Generates and downloads a .pg robotic program file."""
    cfg = load_config(pid)
    if not cfg:
        abort(404, f"Project {pid!r} not found")
    
    sequence = cfg.get("sequence", [])
    total_steps = len(sequence)
    total_thickness = sum(float(step.get("thickness", 0.0)) for step in sequence)
    high_z = 10.0  # App/Retract clearance
    safe_z = 35.0  # Safe Transit Height (below max 40)
    
    # Header
    lines = [
        "Process Main",
        "int speed = 100, acc = 100, dec = 100, cp = 0",
        "int i = 1",
        "int idsrc = 1",
        f"float high = {high_z:.3f}",
        f"float safe = {safe_z:.3f}",
        "float valz = 0.0",
        "float valth = 0.0",
        "float valsz = 0.0",
        "float valapp = 0.0",
        "",
        f"For i = 1 To {total_steps}"
    ]

    # Pre-calculate counts for Source Stack Logic
    from collections import Counter
    # stack_z[src_id] -> current Z (starts at 0.0, decreases)
    stack_z = Counter()     # This tracks Z-height per source location

    # Component Mapping (Auto-assign fallback)
    comp_map = {}
    next_pidx = 1
    
    # Lookup Generation
    for idx, step in enumerate(sequence, 1):
        cid = step.get("comp", f"unknown_{idx}")
        thick_val = float(step.get("thickness", 0.0))
        user_tp = step.get("teachpoint", "")
        
        # Determine Source ID (idsrc)
        src_pidx = 1
        if user_tp and user_tp.upper().startswith("P"):
            # User explicit teachpoint: P5 -> 5
            try:
                src_pidx = int(user_tp.upper().replace("P", ""))
            except ValueError:
                # Fallback if parse fails
                if cid not in comp_map:
                    comp_map[cid] = next_pidx
                    next_pidx += 1
                src_pidx = comp_map[cid]
        else:
            # Auto-map based on component appearance
            if cid not in comp_map:
                comp_map[cid] = next_pidx
                next_pidx += 1
            src_pidx = comp_map[cid]
        
        # Source Stack Ht Calculation (Picking from top down)
        # 1. Get current Z for this stack
        current_z = stack_z[src_pidx]
        
        # 2. Update Z for next pick (decrement by thickness)
        # Note: We assume P1 is taught at TOP of stack.
        # Next pick will be lower.
        stack_z[src_pidx] -= thick_val
        
        prefix = "If" if idx == 1 else "ElseIf"
        lines.append(f"{prefix} i == {idx} Then")
        lines.append(f"valth = {thick_val:.3f}")
        lines.append(f"idsrc = {src_pidx}")
        # Use simple float format for Z
        lines.append(f"valsz = {current_z:.3f}")
    
    if total_steps > 0:
        lines.append("EndIf")
    
    # Motion Logic
    lines.extend([
        "",
        "valapp = valsz + high",
        "MOVJ(Pn(idsrc) + Z(safe, 1), speed, acc, dec, cp)",
        "MOVJ(Pn(idsrc) + Z(valapp, 1), speed, acc, dec, cp)",
        "MOVJ(Pn(idsrc) + Z(valsz, 1), speed, acc, dec, cp)",
        "Open(0)",
        "Open(2)",
        "Delay(200)",
        "MOVJ(Pn(idsrc) + Z(valapp, 1), speed, acc, dec, cp)",
        "MOVJ(Pn(idsrc) + Z(safe, 1), speed, acc, dec, cp)",
        "",
        "valapp = valz + high",
        "MOVJ(Pn(21) + Z(safe, 1), speed, acc, dec, cp)",
        "MOVJ(Pn(21) + Z(valapp, 1), speed, acc, dec, cp)",
        "MOVJ(Pn(21) + Z(valz, 1), speed, acc, dec, cp)",
        "Close(0)",
        "Close(2)",
        "Delay(500)",
        "MOVJ(Pn(21) + Z(valapp, 1), speed, acc, dec, cp)",
        "MOVJ(Pn(21) + Z(safe, 1), speed, acc, dec, cp)",
        "",
        "valz = valz + valth",
        "Next",
        "",
        "MOVJ(Pn(22), speed, acc, dec, cp)",
        "ProcessEnd"
    ])
    
    content = "\r\n".join(lines)
    
    # Debug: Save to local file
    try:
        with open("d:/projects/ags/debug_output.pg", "w") as f:
            f.write(content)
    except Exception as e:
        print(f"Failed to save debug file: {e}")

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment;filename={pid}_program.pg"}
    )
    

# 6) Serve project images --------------------------------------------------
@bp.get("/proj_assets/<pid>/<path:fname>")
def asset(pid: str, fname: str):
    return send_from_directory(PROJECTS / pid / "images", fname)
