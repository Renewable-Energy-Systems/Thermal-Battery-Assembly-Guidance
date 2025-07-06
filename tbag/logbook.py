"""
Shared log/timeline helpers + XLSX export.
"""
import json, hashlib, io
from typing import List, Dict
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from .db import connect
from .projects_helpers import load as load_project

def _hue(name:str)->int:
    return int(hashlib.md5(name.encode()).hexdigest()[:2],16)*360//255

def overview_rows()->List[Dict]:
    rows=[]
    with connect() as c:
        for ts,ev in c.execute(
            "SELECT ts,event FROM events WHERE event LIKE 'session_%' ORDER BY ts DESC"):
            kind,payload=ev.split("::",1)
            if kind=="session_start": continue
            d=json.loads(payload)
            rows.append({"ts":ts,"kind":kind.replace('session_',''),
                         "project":d.get("project"),"stack":d.get("stack_id"),
                         "operator":d.get("operator"),"session":d["session_id"],
                         "step":d.get("interrupted_at"),"hue":_hue(d.get("project",""))})
    return rows

def timeline(sid:str)->List[Dict]:
    with connect() as c:
        cur=c.execute("SELECT ts,event FROM events WHERE event LIKE ? ORDER BY ts",(f"%{sid}%",))
        data=[]
        for ts,raw in cur.fetchall():
            if "::" in raw:
                k,p=raw.split("::",1); p=json.loads(p)
            else: k,p=raw,{}
            data.append({"ts":ts,"kind":k,"payload":p})
        return data

def _sheet(wb:Workbook,title,header,rows):
    ws=wb.create_sheet(title); ws.append(header)
    for r in rows: ws.append(r)
    for col in range(1,len(header)+1):
        ws.column_dimensions[get_column_letter(col)].width=16

def export_overview()->io.BytesIO:
    wb=Workbook(); wb.remove(wb.active)
    dat=overview_rows()
    _sheet(wb,"sessions",
           ["Started","Project","Stack","Operator","Status","Step","Session"],
           [[r["ts"],r["project"],r["stack"],r["operator"],
             r["kind"],(r["step"]+1) if r["step"] else "",r["session"]] for r in dat])
    buf=io.BytesIO(); wb.save(buf); buf.seek(0); return buf

def export_detail(sid)->io.BytesIO:
    wb=Workbook(); wb.remove(wb.active)
    tl=timeline(sid)
    _sheet(wb,"timeline",
           ["Time","Event","Payload"],
           [[e["ts"],e["kind"],json.dumps(e["payload"],separators=(',',':'))] for e in tl])
    buf=io.BytesIO(); wb.save(buf); buf.seek(0); return buf
