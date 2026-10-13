# Campus Customs MCP server

**What it's for:** this is the one way every agent in the project gets shop data. Agents call these tools instead of querying the database themselves. The tools return only what is in the database; if a row doesn't exist, they say "not found" rather than making something up.

**Database:** `data/campus_customs_new.db`, the working copy, opened through `config.get_connection()`. The original `data/campus_customs.db` is never touched; run `python scripts/reset_db.py` to reset the working copy from it.

**Built with:** FastMCP (`pip install fastmcp`). Start it with `python mcp_server/server.py` (from the `hw5` folder).

**Connection:** registered as `campus-customs` in `hw5/.mcp.json` (stdio). Run `python scripts/mcp_smoke_test.py` to call every tool over MCP and check each result against the database; the evidence is saved to `output/mcp_smoke.json`.

## Tools

All tools are read-only. `prepare_*` tools return drafts marked `PENDING_HUMAN_APPROVAL` and write nothing.

| Tool | Inputs | Reads | Returns |
|---|---|---|---|
| `check_inventory` | `sku`, `size` | inventory | name, size, qty in stock, location |
| `get_lease` | `lease_id` | leases | space, landlord, monthly rent, next due, notes |
| `get_pricing` | `sku` | pricing | unit cost and list price |
| `list_open_tickets` | — | tickets | id, type, subject of open tickets |
| `list_tickets` | — | tickets | every ticket with requester and status (open/resolved) |
| `get_ticket` | `ticket_id` | tickets | every field of one ticket |
| `get_shop_date` | — | desk | the shop's "today" and desk notes |
| `list_vendors` | — | vendors | id, name, specialty, lead days |
| `get_cash_balance` | `account` (default `checking`) | cash_accounts | balance and as-of date |
| `get_invoice` | `invoice_id` | invoices | vendor, amount, due date, status, description |
| `find_payments` | `kind`, `ref_id` | payments | payments already made for that rent/invoice |
| `check_margin` | `sku`, `unit_price`, `qty` | pricing | discount %, margin, order profit, above cost? |
| `prepare_payment` | `kind`, `ref_id`, `amount`, `account` | leases or invoices+vendors, cash_accounts, payments | payment draft + any problems (wrong amount, not enough cash, already paid) |
| `prepare_purchase_order` | `vendor_id`, `sku`, `size`, `qty` | vendors, pricing, inventory, desk | PO draft with total cost and lead days |
