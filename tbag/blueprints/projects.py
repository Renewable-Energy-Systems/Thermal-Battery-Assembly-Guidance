from flask import Blueprint, render_template, request, redirect, send_from_directory
import pathlib, uuid
import werkzeug.datastructures
from ..projects_helpers import all_dirs, load, save, new_id
from ..config import PROJECTS

bp = Blueprint("projBP", __name__)

@bp.get("/projects")
def list_projects():
    projs=[{"id":p.name,"name":load(p.name)["name"]} for p in all_dirs()]
    return render_template("project_list.html", projects=projs)

@bp.route("/projects/new", methods=["GET","POST"])
def new():
    if request.method=="POST":
        name=request.form["proj_name"].strip()
        if any(load(p.name)["name"].lower()==name.lower() for p in all_dirs()):
            return render_template("project_new.html", error=f'Project “{name}” exists.')
        pid=new_id(name); save(pid,{"name":name,"sequence":[]})
        return redirect(f"/projects/{pid}/edit")
    return render_template("project_new.html")

@bp.route("/projects/<pid>/edit", methods=["GET","POST"])
def edit(pid):
    cfg=load(pid) or {"name":pid,"sequence":[]}
    if request.method=="POST":
        seq,idx=[],0
        while True:
            lbl=request.form.get(f"label_{idx}")
            if lbl is None: break
            img=cfg["sequence"][idx]["img"] if idx<len(cfg["sequence"]) else None
            fs:werkzeug.datastructures.FileStorage=request.files.get(f"img_{idx}")  # type: ignore
            if fs and fs.filename:
                img=f"step{idx}_{uuid.uuid4().hex[:6]}{pathlib.Path(fs.filename).suffix}"
                fs.save(PROJECTS/pid/"images"/img)
            seq.append({"label":lbl,"img":img}); idx+=1
        cfg["sequence"]=seq; save(pid,cfg); return redirect("/projects")
    return render_template("project_edit.html", project=cfg, sequence=cfg["sequence"])

@bp.get("/proj_assets/<pid>/<path:fname>")
def asset(pid,fname):
    return send_from_directory(PROJECTS/pid/"images", fname)
