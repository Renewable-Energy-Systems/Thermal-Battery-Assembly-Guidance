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
    from ..helpers.settings import load_settings

    cfg = load_config(pid)
    if not cfg:
        abort(404, f"Project {pid!r} not found")

    settings = load_settings()
    tps = settings.get("teachpoints", {})

    sequence   = cfg.get("sequence", [])

    # Global clearance height is taken from P22 Z
    clearance_z = float(tps.get("P22", {}).get("z", 39.0))
    home_tp_name = "P22"
    dest_tp_name = "P21"

    # Pre-calculate pick offsets for each source teachpoint
    # A step's pick offset is the sum of thicknesses of all subsequent items picked from the SAME teachpoint.
    pick_offsets = []
    for i in range(len(sequence)):
        step = sequence[i]
        src_tp = step.get("teachpoint", "P1").strip().upper()
        if not src_tp:
            src_tp = "P1"
        offset = 0.0
        for j in range(i + 1, len(sequence)):
            next_tp = sequence[j].get("teachpoint", "P1").strip().upper()
            if not next_tp:
                next_tp = "P1"
            if next_tp == src_tp:
                offset += float(sequence[j].get("thickness", 0.0))
        pick_offsets.append((src_tp, offset))

    # ── Program header ───────────────────────────────────────────────────────
    lines = [
        "Process Main",
        "",
        "int speed = 40",
        "int acc = 40",
        "int dec = 40",
        "int cp = 0",
        "",
        "User(0)",
        "Tool(0)",
        "",
        "",
        "// --------------------------------------------------",
        "// MOVE TO HOME POSITION (Pn22)",
        "// --------------------------------------------------",
        "MOVJ(Pn(22), speed, acc, dec, cp)",
        "",
        ""
    ]

    dest_z_offset = 0.0   # accumulates target Z height per stacked layer
    
    for step_idx, (step, (src_tp, src_z_offset)) in enumerate(zip(sequence, pick_offsets), 1):
        thick_val = float(step.get("thickness", 0.0))
        label     = step.get("label", f"Component {step_idx}").strip() or f"Component {step_idx}"

        # Resolve source TP coordinates
        src_t_data = tps.get(src_tp, tps.get("P1", {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0}))
        src_x = float(src_t_data.get("x", 0.0))
        src_y = float(src_t_data.get("y", 0.0))
        src_base_z = float(src_t_data.get("z", 0.0))
        src_r = float(src_t_data.get("r", 0.0))
        
        pick_z = src_base_z + src_z_offset

        # Resolve dest TP coordinates
        dest_t_data = tps.get(dest_tp_name, {"x": 0.0, "y": 0.0, "z": 0.0, "r": 0.0})
        dest_x = float(dest_t_data.get("x", 0.0))
        dest_y = float(dest_t_data.get("y", 0.0))
        dest_base_z = float(dest_t_data.get("z", 0.0))
        dest_r = float(dest_t_data.get("r", 0.0))
        
        place_z = dest_base_z + dest_z_offset

        cx = f"{clearance_z:g}"
        sx = f"{src_x:g}"; sy = f"{src_y:g}"; sr = f"{src_r:g}"
        dx = f"{dest_x:g}"; dy = f"{dest_y:g}"; dr = f"{dest_r:g}"
        pz = f"{pick_z:g}"
        plz = f"{place_z:g}"
        sbz = f"{src_base_z:g}"
        dbz = f"{dest_base_z:g}"

        lines.append("// ==================================================")
        if step_idx == 1:
            lines.append(f"// PICK {step_idx}  (Top component at {src_tp})")
            lines.append(f"// Base Z = {sbz}")
            total_comps = sum(1 for tp, _ in pick_offsets if tp == src_tp)
            if total_comps > 1:
                lines.append(f"// {total_comps} components \u00d7 {thick_val:g}mm")
            lines.append(f"// Top Z = {pz}")
        elif step_idx == len(sequence):
            lines.append(f"// PICK {step_idx}  (Last component, base Z = {sbz})")
        else:
            lines.append(f"// PICK {step_idx}  (Z = {pz})")
        lines.append("// ==================================================")
        lines.append("")

        if step_idx == 1:
            lines.append(f"// Move above {src_tp} at global clearance height")
            lines.append(f"MOVL(BuildPoint({sx},{sy},{cx},{sr},1), speed, acc, dec, cp)")
            lines.append("")
            lines.append(f"// Descend to top component ({pz})")
            lines.append(f"MOVL(BuildPoint({sx},{sy},{pz},{sr},1), speed, acc, dec, cp)")
            lines.append("Delay(1000)")
            lines.append("")
            lines.append("// Retract vertically to clearance")
            lines.append(f"MOVL(BuildPoint({sx},{sy},{cx},{sr},1), speed, acc, dec, cp)")
            lines.append("")
            lines.append("")
        else:
            lines.append(f"MOVL(BuildPoint({sx},{sy},{cx},{sr},1), speed, acc, dec, cp)")
            lines.append(f"MOVL(BuildPoint({sx},{sy},{pz},{sr},1), speed, acc, dec, cp)")
            lines.append("Delay(1000)")
            lines.append(f"MOVL(BuildPoint({sx},{sy},{cx},{sr},1), speed, acc, dec, cp)")
            lines.append("")
            lines.append("")

        if step_idx == 1:
            lines.append(f"// Place at {dest_tp_name} level 1 (stack base = {dbz})")
            lines.append(f"MOVL(BuildPoint({dx},{dy},{cx},{dr},1), speed, acc, dec, cp)")
            lines.append(f"MOVL(BuildPoint({dx},{dy},{plz},{dr},1), speed, acc, dec, cp)")
            lines.append("Delay(1000)")
            lines.append(f"MOVL(BuildPoint({dx},{dy},{cx},{dr},1), speed, acc, dec, cp)")
            lines.append("")
            lines.append("")
        else:
            lines.append(f"// Place level {step_idx} ({plz})")
            lines.append(f"MOVL(BuildPoint({dx},{dy},{cx},{dr},1), speed, acc, dec, cp)")
            lines.append(f"MOVL(BuildPoint({dx},{dy},{plz},{dr},1), speed, acc, dec, cp)")
            lines.append("Delay(1000)")
            lines.append(f"MOVL(BuildPoint({dx},{dy},{cx},{dr},1), speed, acc, dec, cp)")
            lines.append("")
            lines.append("")

        dest_z_offset += thick_val

    # ── Return to home P22 ───────────────────────────────────────────────────
    lines.append("// --------------------------------------------------")
    lines.append("// RETURN TO HOME")
    lines.append("// --------------------------------------------------")
    lines.append("MOVJ(Pn(22), speed, acc, dec, cp)")
    lines.append("")
    lines.append("ProcessEnd")

    content = "\r\n".join(lines)

    # Debug: save a local copy for inspection
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
