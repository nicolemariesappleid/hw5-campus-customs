"""Campus Customs backend API for the React dashboard.

Start (from the backend/ folder):  uvicorn main:app --reload --port 8000

SIMULATION ONLY: the shop is fake. No real money moves and no emails are sent.
Agents only read data and prepare drafts; POST /approvals/{id}/approve (a human click)
is the only route that changes cash, and it only updates the local SQLite working copy.
"""
import asyncio
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `backend.*` and `config` import from backend/
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend import approvals, audit  # noqa: E402
from backend.team import build_team, mcp, run_ticket  # noqa: E402
from config import DB_PATH, ORIGINAL_DB, get_connection  # noqa: E402

_team = None
_run_lock = asyncio.Lock()  # one agent run at a time (keeps token spend predictable)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp:  # one MCP server process for the backend's lifetime
        yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.add_middleware(CORSMiddleware,  # let the Vite dev page (npm run dev) call this API
                   allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/tickets")
async def tickets():
    """All tickets with open/resolved status, plus the Boss's latest decision if any."""
    decisions = approvals.load()["decisions"]
    rows = await mcp.direct_call_tool("list_tickets", {})
    return [{**t, "decision": decisions.get(str(t["id"]))} for t in rows]


@app.post("/tickets/{ticket_id}/run")
async def run(ticket_id: int):
    """Run the agent team on one ticket. Returns the Boss's final decision and token usage."""
    global _team
    ticket = await mcp.direct_call_tool("get_ticket", {"ticket_id": ticket_id})
    if not ticket.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")
    if _run_lock.locked():
        raise HTTPException(409, "Another ticket is running; try again when it finishes.")
    async with _run_lock:
        if _team is None:
            try:
                _team = build_team()
            except RuntimeError as e:  # e.g. PORTKEY_API_KEY not set
                raise HTTPException(500, str(e))
        result = await run_ticket(_team, ticket_id)
    result["pending_approvals"] = [a for a in approvals.load()["approvals"]
                                   if a["ticket_id"] == ticket_id and a["status"] == "pending"]
    return result


@app.get("/events")
def events(after: int = -1, ticket_id: int | None = None, limit: int = 100):
    """Recent agent events: who spoke, what they said, which tools they called.
    Poll with ?after=<last id> to get only new events."""
    trail = json.loads(audit.AUDIT_PATH.read_text()) if audit.AUDIT_PATH.exists() else []
    out = []
    for i, e in enumerate(trail):
        if i <= after or (ticket_id is not None and e.get("ticket_id") != ticket_id):
            continue
        if e["event"] == "step" and e["kind"] not in ("model_response", "end"):
            continue  # skip prompt/tool-return plumbing; the board needs what agents said and did
        item = {"id": i, "ts": e["ts"], "event": e["event"], "ticket_id": e.get("ticket_id"),
                "run_id": e.get("run_id")}
        if e["event"] == "step":
            parts = e.get("parts", [])
            item.update(
                agent=e["agent"], called_by=e["called_by"], depth=e["depth"],
                said=" ".join(p["content"] for p in parts if p["kind"] == "text") or None,
                tools=[{"tool": p["tool"], "args": p["args"]} for p in parts
                       if p["kind"] == "tool-call" and p["tool"] != "final_result"],
                output=e.get("output"),
            )
        else:
            item.update({k: e[k] for k in ("decision", "error", "usage") if k in e})
        out.append(item)
    return out[-limit:]


@app.get("/approvals")
def list_approvals(status: str | None = "pending"):
    """Payment / purchase-order drafts the agents prepared (default: still pending)."""
    items = approvals.load()["approvals"]
    return [a for a in items if status is None or a["status"] == status]


class ApproveBody(BaseModel):
    approved_by: str = "human"


@app.post("/approvals/{approval_id}/approve")
def approve(approval_id: int, body: ApproveBody = ApproveBody()):
    """Human approves a drafted payment or PO. Re-checks the DB, then records it and lowers cash.
    Simulated: only the local SQLite file changes."""
    try:
        result = approvals.approve(approval_id, body.approved_by)
    except approvals.ApprovalError as e:
        audit.append({"event": "approval_rejected", "approval_id": approval_id, "reason": str(e)})
        raise HTTPException(409, str(e))
    a = result["approval"]
    audit.append({"event": "approval", "approval_id": approval_id, "ticket_id": a["ticket_id"], "type": a["type"],
                  "amount": a["amount"], "approved_by": a["approved_by"], "draft": a["draft"],
                  "new_balance": result["new_balance"]})
    return result


@app.get("/cash")
async def cash():
    """Current checking balance from cash_accounts."""
    return await mcp.direct_call_tool("get_cash_balance", {"account": "checking"})


@app.post("/reset")
def reset():
    """Restore data/campus_customs_new.db from the original and clear pending approvals.
    The audit trail is kept (it is append-only)."""
    if _run_lock.locked():
        raise HTTPException(409, "Can't reset while a ticket is running.")
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    DB_PATH.chmod(0o644)
    approvals.clear()
    with get_connection() as conn:
        start = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()[0]
    audit.append({"event": "reset", "detail": f"{DB_PATH.name} restored from {ORIGINAL_DB.name}",
                  "starting_checking_balance": start})
    return {"reset": True, "database": DB_PATH.name}
