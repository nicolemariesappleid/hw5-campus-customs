"""Human approval queue + the ONLY code that changes cash.

Agents can only *prepare* payments and purchase orders (MCP prepare_* tools, read-only).
Those drafts land here as "pending". A human clicking Approve calls approve(), which
re-checks everything against the database and then records the payment.

SIMULATION ONLY: this shop is fake. "Paying" just updates rows in
data/campus_customs_new.db. No bank, payment API or email is ever contacted.
"""
import json
import os
from datetime import datetime, timezone

from config import PROJECT_DIR, get_connection

STATE_PATH = PROJECT_DIR / "output" / "desk_state.json"
PREPARE_TOOLS = {"prepare_payment": "payment", "prepare_purchase_order": "purchase_order"}


# --- state file: pending approvals + latest Boss decision per ticket -------------------
def load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"approvals": [], "decisions": {}}


def save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, STATE_PATH)


def clear() -> None:
    save({"approvals": [], "decisions": {}})


def capture(run_id: str, ticket_id: int | None, tool: str, result) -> None:
    """Called by the agent loop whenever a prepare_* tool returns. Queues valid drafts."""
    if tool not in PREPARE_TOOLS:
        return
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return
    if not isinstance(result, dict) or not result.get("ok"):
        return
    state = load()
    draft = result["draft"]
    if any(a["status"] == "pending" and a["ticket_id"] == ticket_id and a["draft"] == draft
           for a in state["approvals"]):
        return  # same draft already waiting
    state["approvals"].append({
        "id": len(state["approvals"]) + 1, "ticket_id": ticket_id, "run_id": run_id,
        "type": PREPARE_TOOLS[tool], "draft": draft, "status": "pending",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    save(state)


def record_decision(ticket_id: int, decision: dict) -> None:
    state = load()
    state["decisions"][str(ticket_id)] = decision
    save(state)
    _set_ticket_status(ticket_id, "resolved")  # the run finished; any money still waits in the approval queue


def _pending_for(state: dict, ticket_id: int) -> list:
    return [a for a in state["approvals"] if a["ticket_id"] == ticket_id and a["status"] == "pending"]


def _set_ticket_status(ticket_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))


# --- the human-only money path ----------------------------------------------------------
class ApprovalError(Exception):
    pass


def approve(approval_id: int, approved_by: str) -> dict:
    state = load()
    item = next((a for a in state["approvals"] if a["id"] == approval_id), None)
    if item is None:
        raise ApprovalError(f"No approval #{approval_id}.")
    if item["status"] != "pending":
        raise ApprovalError(f"Approval #{approval_id} is already {item['status']}.")
    d = item["draft"]

    conn = get_connection()
    try:
        with conn:  # one transaction: all checks + writes succeed together or not at all
            today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]
            account = d.get("account", "checking")
            cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
            if cash is None:
                raise ApprovalError(f"No cash account '{account}'.")

            if item["type"] == "payment":
                kind, ref_id, amount = d["kind"], d["ref_id"], float(d["amount"])
                if conn.execute("SELECT 1 FROM payments WHERE kind = ? AND ref_id = ?", (kind, ref_id)).fetchone():
                    raise ApprovalError(f"This {kind} (#{ref_id}) is already paid.")
                if kind == "invoice":
                    inv = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
                    if inv is None or inv["status"] != "open" or inv["amount"] != amount:
                        raise ApprovalError("Invoice is missing, not open, or the amount changed.")
                else:
                    lease = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
                    if lease is None or lease["monthly_rent"] != amount:
                        raise ApprovalError("Lease is missing or the rent amount changed.")
            else:  # purchase order: re-price from the database, never trust the draft's total
                kind, ref_id = "purchase_order", d["vendor_id"]
                unit = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (d["sku"],)).fetchone()
                if unit is None:
                    raise ApprovalError(f"No pricing for {d['sku']}.")
                amount = round(unit["unit_cost"] * int(d["qty"]), 2)

            if amount <= 0 or amount > cash["balance"]:
                raise ApprovalError(f"Not enough cash: {amount:.2f} needed, {cash['balance']:.2f} in {account}.")

            conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
                (kind, ref_id, amount, account, today, approved_by),
            )
            conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                         (amount, today, account))
            if kind == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            new_balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()[0]
    finally:
        conn.close()

    item.update(status="approved", approved_by=approved_by, amount=amount,
                approved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    save(state)
    tid = item["ticket_id"]
    decision = state["decisions"].get(str(tid), {})
    if tid and not _pending_for(state, tid) and decision.get("status") != "blocked":
        _set_ticket_status(tid, "resolved")
    return {"approval": item, "account": account, "new_balance": new_balance, "simulated": True}
