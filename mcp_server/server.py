"""Campus Customs MCP server.

Every agent in this project gets shop data through these tools. They only read
data/campus_customs_new.db (via config.get_connection) and return exactly what
is in the database. If a row is missing, the tool says so instead of guessing.

Run later with:  python mcp_server/server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP  # noqa: E402

from config import DB_PATH, get_connection  # noqa: E402

mcp = FastMCP("campus-customs")


def _query(sql: str, params: tuple) -> list[dict]:
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


@mcp.tool
def check_inventory(sku: str, size: str) -> dict:
    """Look up how many units of one SKU in one size are in stock.

    Reads the inventory table. Use for customer orders (e.g. ticket 101)
    to see whether the requested item and size can be filled.
    """
    rows = _query(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku, size),
    )
    if not rows:
        return {"found": False, "sku": sku, "size": size,
                "message": "No inventory row for this SKU and size in the database."}
    return {"found": True, **rows[0]}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up a lease: space, landlord, monthly rent, and next due date.

    Reads the leases table. Use for rent notices (e.g. ticket 102) to confirm
    the amount and due date before any rent payment is considered.
    """
    rows = _query(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        (lease_id,),
    )
    if not rows:
        return {"found": False, "lease_id": lease_id,
                "message": "No lease with this id in the database."}
    return {"found": True, **rows[0]}


@mcp.tool
def get_pricing(sku: str) -> dict:
    """Look up the unit cost and list price for one SKU.

    Reads the pricing table. Use for discount requests (e.g. ticket 103) to
    see the list price and the cost floor a discount must stay above.
    """
    rows = _query("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not rows:
        return {"found": False, "sku": sku,
                "message": "No pricing row for this SKU in the database."}
    return {"found": True, **rows[0]}


def _one(sql: str, params: tuple, what: str) -> dict:
    rows = _query(sql, params)
    return {"found": True, **rows[0]} if rows else {"found": False, "message": f"No {what} in the database."}


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List open tickets (id, type, subject). Reads tickets."""
    return _query("SELECT id, type, subject FROM tickets WHERE status = 'open' ORDER BY id", ())


@mcp.tool
def list_tickets() -> list[dict]:
    """List every ticket with its status (open or resolved). Reads tickets."""
    return _query("SELECT id, type, requester, subject, status FROM tickets ORDER BY id", ())


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with all its fields. Reads tickets."""
    return _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,), f"ticket {ticket_id}")


@mcp.tool
def get_shop_date() -> dict:
    """Get the shop's current date ('today') and desk notes. Reads desk."""
    return _one("SELECT date_today, notes FROM desk LIMIT 1", (), "desk row")


@mcp.tool
def list_vendors() -> list[dict]:
    """List vendors with specialty and lead time in days. Reads vendors."""
    return _query("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id", ())


@mcp.tool
def get_cash_balance(account: str = "checking") -> dict:
    """Get the balance of one cash account. Reads cash_accounts."""
    return _one("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,),
                f"cash account '{account}'")


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Get one vendor invoice (amount, due date, status). Reads invoices."""
    return _one("SELECT * FROM invoices WHERE id = ?", (invoice_id,), f"invoice {invoice_id}")


@mcp.tool
def find_payments(kind: str, ref_id: int) -> list[dict]:
    """List payments already made for a lease ('rent') or invoice ('invoice') id. Reads payments.
    Use before preparing any payment to avoid paying twice."""
    return _query("SELECT * FROM payments WHERE kind = ? AND ref_id = ?", (kind, ref_id))


@mcp.tool
def check_margin(sku: str, unit_price: float, qty: int) -> dict:
    """Compute margin for selling qty units of a SKU at unit_price. Reads pricing."""
    p = _one("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,), f"pricing for {sku}")
    if not p["found"]:
        return p
    cost, lst = p["unit_cost"], p["list_price"]
    return {
        "found": True, "sku": sku, "qty": qty, "unit_price": unit_price,
        "unit_cost": cost, "list_price": lst,
        "discount_pct": round((lst - unit_price) / lst * 100, 1),
        "unit_margin": round(unit_price - cost, 2),
        "margin_pct": round((unit_price - cost) / unit_price * 100, 1) if unit_price else None,
        "order_revenue": round(unit_price * qty, 2),
        "order_profit": round((unit_price - cost) * qty, 2),
        "above_cost": unit_price > cost,
    }


@mcp.tool
def prepare_payment(kind: str, ref_id: int, amount: float, account: str = "checking") -> dict:
    """Draft a rent ('rent', ref_id=lease id) or invoice ('invoice', ref_id=invoice id) payment
    for HUMAN APPROVAL. Reads leases/invoices, cash_accounts, payments. Writes nothing; moves no money."""
    if kind == "rent":
        ref = _one("SELECT monthly_rent AS amount_due, next_due AS due_date, landlord AS payee "
                   "FROM leases WHERE id = ?", (ref_id,), f"lease {ref_id}")
    elif kind == "invoice":
        ref = _one("SELECT i.amount AS amount_due, i.due_date, i.status, v.name AS payee FROM invoices i "
                   "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (ref_id,), f"invoice {ref_id}")
    else:
        return {"ok": False, "problems": ["kind must be 'rent' or 'invoice'"]}
    if not ref["found"]:
        return {"ok": False, "problems": [ref["message"]]}
    cash = get_cash_balance(account)
    paid = find_payments(kind, ref_id)
    problems = []
    if amount <= 0:
        problems.append("amount must be positive")
    if amount != ref["amount_due"]:
        problems.append(f"amount {amount} differs from amount due {ref['amount_due']}")
    if not cash["found"]:
        problems.append(cash["message"])
    elif amount > cash["balance"]:
        problems.append(f"amount exceeds {account} balance {cash['balance']}")
    if kind == "invoice" and ref.get("status") != "open":
        problems.append(f"invoice status is '{ref.get('status')}', not open")
    if paid:
        problems.append(f"{len(paid)} payment(s) already recorded for this {kind}")
    return {
        "ok": not problems, "problems": problems, "status": "PENDING_HUMAN_APPROVAL",
        "draft": {"kind": kind, "ref_id": ref_id, "payee": ref["payee"], "amount": amount,
                  "account": account, "due_date": ref["due_date"]},
        "balance_before": cash.get("balance"),
        "balance_after": round(cash["balance"] - amount, 2) if cash["found"] else None,
    }


@mcp.tool
def prepare_purchase_order(vendor_id: int, sku: str, size: str, qty: int) -> dict:
    """Draft a restock purchase order for HUMAN APPROVAL, costed at unit_cost.
    Reads vendors, pricing, inventory, desk. Writes nothing."""
    vendor = _one("SELECT name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,),
                  f"vendor {vendor_id}")
    price = _one("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,), f"pricing for {sku}")
    stock = check_inventory(sku, size)
    problems = [r["message"] for r in (vendor, price, stock) if not r["found"]]
    if qty <= 0:
        problems.append("qty must be positive")
    if problems:
        return {"ok": False, "problems": problems}
    today = get_shop_date().get("date_today")
    return {
        "ok": True, "status": "PENDING_HUMAN_APPROVAL",
        "draft": {"vendor_id": vendor_id, "vendor": vendor["name"], "sku": sku, "size": size,
                  "qty": qty, "unit_cost": price["unit_cost"],
                  "total_cost": round(price["unit_cost"] * qty, 2),
                  "lead_days": vendor["lead_days"], "ordered_on": today},
        "on_hand_now": stock["qty"],
    }


if __name__ == "__main__":
    print(f"campus-customs MCP server using {DB_PATH}", file=sys.stderr)
    mcp.run(show_banner=False)
