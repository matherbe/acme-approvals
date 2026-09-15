"""Acme Approvals: a small fictional SaaS admin for AI Lab Keys demos.

One file. Serves the UI on /, a REST API under /api, OpenAPI docs at /docs.
State lives in acme.db (SQLite) next to this file. Run: python app.py
"""
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

DB = Path(__file__).with_name("acme.db")
API_KEY = os.environ.get("ACME_API_KEY", "")  # empty = no auth (demo default)
PORT = int(os.environ.get("ACME_PORT", "8080"))
HOST = os.environ.get("ACME_HOST", "127.0.0.1")  # 0.0.0.0 to reach it from another VM in the environment

app = FastAPI(title="Acme Approvals API", version="1.0.0",
              description="Approval workflows for Acme Inc. Fictional demo product.")


# ---------- storage ----------

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    fresh = not DB.exists()
    with closing(db()) as conn, conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            approver TEXT NOT NULL,
            threshold REAL NOT NULL DEFAULT 1000,
            notify_requester INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL REFERENCES workflows(id),
            requester TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            message TEXT NOT NULL,
            at REAL NOT NULL
        );
        """)
        if fresh:
            now = time.time()
            wf = [
                ("Software purchases", "Priya Nair", 2500, 1),
                ("Travel and expenses", "Tom Achebe", 800, 1),
                ("Contractor onboarding", "Maria Santos", 5000, 0),
            ]
            conn.executemany(
                "INSERT INTO workflows(name, approver, threshold, notify_requester, active, updated_at) VALUES (?,?,?,?,1,?)",
                [(n, a, t, nt, now) for n, a, t, nt in wf])
            reqs = [
                (1, "Dev team", "JetBrains licenses, 12 seats", 3480, "pending"),
                (1, "Design", "Figma professional, 4 seats", 720, "approved"),
                (2, "Sales", "Flights and hotel, Sydney customer visit", 1240, "pending"),
                (2, "Support", "Conference pass, SupportWorld", 650, "approved"),
                (3, "Engineering", "Contract SRE, 3 months", 42000, "pending"),
                (1, "Marketing", "Webinar platform annual plan", 2200, "rejected"),
            ]
            conn.executemany(
                "INSERT INTO requests(workflow_id, requester, description, amount, status, created_at) VALUES (?,?,?,?,?,?)",
                [(w, r, d, a, s, now - i * 3600) for i, (w, r, d, a, s) in enumerate(reqs)])
            conn.execute("INSERT INTO activity(actor, message, at) VALUES (?,?,?)",
                         ("system", "Demo data loaded", now))


def log(conn, actor: str, message: str):
    conn.execute("INSERT INTO activity(actor, message, at) VALUES (?,?,?)", (actor, message, time.time()))


def require_key(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def actor_from(x_actor: Optional[str]) -> str:
    return (x_actor or "api").strip()[:40]


# ---------- models ----------

class WorkflowIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    approver: str = Field(..., min_length=2, max_length=60)
    threshold: float = Field(1000, ge=0)
    notify_requester: bool = True


class WorkflowPatch(BaseModel):
    approver: Optional[str] = None
    threshold: Optional[float] = Field(default=None, ge=0)
    notify_requester: Optional[bool] = None
    active: Optional[bool] = None


class RequestIn(BaseModel):
    workflow_id: int
    requester: str
    description: str
    amount: float = Field(..., ge=0)


class Decision(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|pending)$")


# ---------- API ----------

@app.get("/api/workflows", dependencies=[Depends(require_key)])
def list_workflows():
    with closing(db()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM workflows ORDER BY id")]


@app.post("/api/workflows", status_code=201, dependencies=[Depends(require_key)])
def create_workflow(body: WorkflowIn, x_actor: Optional[str] = Header(default=None)):
    with closing(db()) as conn, conn:
        try:
            cur = conn.execute(
                "INSERT INTO workflows(name, approver, threshold, notify_requester, active, updated_at) VALUES (?,?,?,?,1,?)",
                (body.name, body.approver, body.threshold, int(body.notify_requester), time.time()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, f"Workflow '{body.name}' already exists")
        log(conn, actor_from(x_actor), f"Created workflow '{body.name}' (approver {body.approver}, threshold ${body.threshold:,.0f})")
        return dict(conn.execute("SELECT * FROM workflows WHERE id=?", (cur.lastrowid,)).fetchone())


@app.patch("/api/workflows/{wf_id}", dependencies=[Depends(require_key)])
def update_workflow(wf_id: int, body: WorkflowPatch, x_actor: Optional[str] = Header(default=None)):
    with closing(db()) as conn, conn:
        row = conn.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Workflow not found")
        changes = []
        if body.approver is not None:
            conn.execute("UPDATE workflows SET approver=? WHERE id=?", (body.approver, wf_id))
            changes.append(f"approver to {body.approver}")
        if body.threshold is not None:
            conn.execute("UPDATE workflows SET threshold=? WHERE id=?", (body.threshold, wf_id))
            changes.append(f"threshold to ${body.threshold:,.0f}")
        if body.notify_requester is not None:
            conn.execute("UPDATE workflows SET notify_requester=? WHERE id=?", (int(body.notify_requester), wf_id))
            changes.append(f"notify requester {'on' if body.notify_requester else 'off'}")
        if body.active is not None:
            conn.execute("UPDATE workflows SET active=? WHERE id=?", (int(body.active), wf_id))
            changes.append("activated" if body.active else "paused")
        if not changes:
            raise HTTPException(400, "Nothing to update")
        conn.execute("UPDATE workflows SET updated_at=? WHERE id=?", (time.time(), wf_id))
        log(conn, actor_from(x_actor), f"Updated '{row['name']}': " + ", ".join(changes))
        return dict(conn.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone())


@app.get("/api/requests", dependencies=[Depends(require_key)])
def list_requests(status: Optional[str] = None, workflow_id: Optional[int] = None):
    q = "SELECT r.*, w.name AS workflow FROM requests r JOIN workflows w ON w.id=r.workflow_id WHERE 1=1"
    args = []
    if status:
        q += " AND r.status=?"; args.append(status)
    if workflow_id:
        q += " AND r.workflow_id=?"; args.append(workflow_id)
    q += " ORDER BY r.created_at DESC"
    with closing(db()) as conn:
        return [dict(r) for r in conn.execute(q, args)]


@app.post("/api/requests", status_code=201, dependencies=[Depends(require_key)])
def create_request(body: RequestIn, x_actor: Optional[str] = Header(default=None)):
    with closing(db()) as conn, conn:
        wf = conn.execute("SELECT * FROM workflows WHERE id=?", (body.workflow_id,)).fetchone()
        if not wf:
            raise HTTPException(404, "Workflow not found")
        cur = conn.execute(
            "INSERT INTO requests(workflow_id, requester, description, amount, status, created_at) VALUES (?,?,?,?,'pending',?)",
            (body.workflow_id, body.requester, body.description, body.amount, time.time()))
        log(conn, actor_from(x_actor), f"New request in '{wf['name']}': {body.description} (${body.amount:,.0f})")
        return dict(conn.execute("SELECT * FROM requests WHERE id=?", (cur.lastrowid,)).fetchone())


@app.post("/api/requests/{req_id}/decision", dependencies=[Depends(require_key)])
def decide_request(req_id: int, body: Decision, x_actor: Optional[str] = Header(default=None)):
    with closing(db()) as conn, conn:
        row = conn.execute("SELECT r.*, w.name AS workflow FROM requests r JOIN workflows w ON w.id=r.workflow_id WHERE r.id=?", (req_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Request not found")
        conn.execute("UPDATE requests SET status=? WHERE id=?", (body.status, req_id))
        log(conn, actor_from(x_actor), f"{body.status.capitalize()} request #{req_id}: {row['description']}")
        return dict(conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone())


@app.get("/api/activity", dependencies=[Depends(require_key)])
def activity(limit: int = 20):
    with closing(db()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,))]


@app.post("/api/reset", dependencies=[Depends(require_key)])
def reset():
    """Wipe and reseed demo data. Handy between takes."""
    if DB.exists():
        DB.unlink()
    init_db()
    return {"ok": True}


# ---------- UI ----------

INDEX = """<!doctype html><html><head><meta charset="utf-8"><title>Acme Approvals</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script>if(!location.pathname.endsWith('/')){location.replace(location.pathname+'/'+location.search);}</script>
<style>
:root{--ink:#1d1a6b;--ink2:#2b2a8a;--pink:#ff2874;--bg:#f6f5fb;--line:#e4e1f1;--muted:#6b6b8a}
*{box-sizing:border-box}body{margin:0;font-family:Poppins,Inter,system-ui,sans-serif;background:var(--bg);color:#1c1c2e;display:grid;grid-template-columns:220px 1fr;min-height:100vh}
aside{background:var(--ink);color:#fff;padding:26px 22px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;margin-bottom:34px}
.brand span{background:#fff;color:var(--ink);border-radius:8px;width:30px;height:30px;display:grid;place-items:center;font-size:16px}
nav a{display:block;color:#cfd0ee;text-decoration:none;padding:9px 12px;border-radius:8px;font-size:14px;margin-bottom:4px}
nav a.on{background:#3e3d9e;color:#fff}
main{padding:34px 40px;max-width:1100px}
h1{color:var(--ink);font-size:30px;margin:0 0 6px}.sub{color:var(--muted);margin:0 0 26px;font-size:14px}
.grid{display:grid;grid-template-columns:1.6fr 1fr;gap:22px;align-items:start}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:14px}
.card h3{margin:0 0 4px;color:var(--ink);font-size:17px}.meta{color:var(--muted);font-size:13px}
.row{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:12px;padding:10px 12px;background:var(--bg);border-radius:8px;font-size:14px}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600}
.on{background:#dff5ea;color:#177245}.off{background:#f1f0f7;color:var(--muted)}.paused{background:#fde7ef;color:#b3134f}
.toggle{width:46px;height:26px;border-radius:13px;background:#c9c8dd;position:relative;flex:none}
.toggle.t{background:var(--ink)}.toggle::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;transition:left .2s}
.toggle.t::after{left:23px}
table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:var(--muted);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line)}td{padding:8px;border-bottom:1px solid var(--line)}
.st{font-weight:600}.st.pending{color:#a06400}.st.approved{color:#177245}.st.rejected{color:#b3134f}
.feed li{list-style:none;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}.feed{padding:0;margin:0}
.who{display:inline-block;background:var(--ink);color:#fff;border-radius:6px;padding:1px 7px;font-size:11px;margin-right:8px;font-family:ui-monospace,Consolas,monospace}
.who.agent{background:var(--pink)}
.flash{animation:fl 1.6s ease-out}@keyframes fl{from{background:#fff0f5}to{background:#fff}}
.hdr{display:flex;justify-content:space-between;align-items:baseline}
.live{font-size:12px;color:var(--muted)}.live b{color:#177245}
</style></head><body>
<aside><div class="brand"><span>A</span>Acme</div>
<nav><a>Dashboard</a><a>Requests</a><a class="on">Approval workflows</a><a>Team</a><a>Settings</a></nav></aside>
<main>
<div class="hdr"><div><h1>Approval workflows</h1><p class="sub">Who approves what, and above which amount.</p></div><div class="live">Live <b>●</b> <span id="ts"></span></div></div>
<div class="grid"><div id="wf"></div>
<div><div class="card"><h3>Pending requests</h3><table id="req"></table></div>
<div class="card"><h3>Activity</h3><ul class="feed" id="feed"></ul></div></div></div>
</main>
<script>
const KEY = new URLSearchParams(location.search).get('key') || '';
const H = KEY ? {'X-API-Key': KEY} : {};
const money = n => '$' + Number(n).toLocaleString(undefined,{maximumFractionDigits:0});
let last = {};
async function j(u){const r = await fetch(u,{headers:H}); return r.json();}
async function refresh(){
  const [w, r, a] = await Promise.all([j('api/workflows'), j('api/requests?status=pending'), j('api/activity?limit=8')]);
  const wf = document.getElementById('wf'); wf.innerHTML = w.map(x => {
    const changed = last[x.id] && last[x.id] !== x.updated_at; last[x.id] = x.updated_at;
    return `<div class="card ${changed?'flash':''}"><div class="hdr"><h3>${x.name}</h3><span class="pill ${x.active?'on':'paused'}">${x.active?'Active':'Paused'}</span></div>
    <div class="meta">Approver: <b>${x.approver}</b></div>
    <div class="row"><span>Requires approval above</span><b>${money(x.threshold)}</b></div>
    <div class="row"><span>Notify requester on decision</span><span class="toggle ${x.notify_requester?'t':''}"></span></div></div>`}).join('');
  document.getElementById('req').innerHTML = '<tr><th>Request</th><th>Amount</th><th>Status</th></tr>' +
    (r.length ? r.map(x=>`<tr><td>${x.description}<div class="meta">${x.requester} · ${x.workflow}</div></td><td>${money(x.amount)}</td><td class="st ${x.status}">${x.status}</td></tr>`).join('') : '<tr><td colspan=3 class="meta">Nothing pending</td></tr>');
  document.getElementById('feed').innerHTML = a.map(x=>`<li><span class="who ${/agent|claude|mcp/i.test(x.actor)?'agent':''}">${x.actor}</span>${x.message}</li>`).join('');
  document.getElementById('ts').textContent = new Date().toLocaleTimeString();
}
refresh(); setInterval(refresh, 2000);
</script></body></html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return INDEX


@app.get("/health", include_in_schema=False)
def health():
    return JSONResponse({"ok": True, "auth": bool(API_KEY)})


init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
