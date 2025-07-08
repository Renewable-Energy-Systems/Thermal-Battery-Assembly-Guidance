"""
Shared log/timeline helpers + XLSX export.
"""
import json, hashlib, io
import sqlite3
from typing import List, Dict
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from .db import connect
from .projects_helpers import load as load_project

def _hue(name:str)->int:
    return int(hashlib.md5(name.encode()).hexdigest()[:2],16)*360//255

def overview_rows() -> list[dict]:
    """
    One dict per run, newest first.
    Data comes directly from the `runs` table, not from the events table.
    """
    rows: list[dict] = []
    with connect() as c:
        c.row_factory = sqlite3.Row
        for r in c.execute(
            "SELECT ts_created, project, stack_id, operator, status, "
            "       interrupted_at, session_id "
            "FROM runs ORDER BY ts_created DESC"
        ).fetchall():

            # map DB → fields expected by the template
            kind = "end" if r["status"] == "finished" else "abort"
            rows.append({
                "ts":        r["ts_created"],
                "project":   r["project"],
                "stack_id":  r["stack_id"],
                "operator":  r["operator"],
                "kind":      kind,
                "step":      r["interrupted_at"],
                "session_id":r["session_id"],
                "hue":       _hue(r["project"]),
            })
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
