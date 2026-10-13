# Campus Customs Agent Harness

Contents: database tables · MCP tools · the five agents · backend API routes · dashboard · full run and reports · safety rules.

Source: `data/campus_customs.db` (original, read-only). Agents work on `data/campus_customs_new.db`.
All agents use `gpt-6-luna` through Portkey.

## Database tables

### desk
Fields: `date_today` (TEXT), `notes` (TEXT)
Why it matters: sets the shop's "today" (2026-08-31) that agents use to judge due dates and whether something is overdue.

### inventory
Fields: `sku` (TEXT), `name` (TEXT), `size` (TEXT), `qty` (INTEGER), `location` (TEXT). Key: (`sku`, `size`)
Why it matters: tells agents whether a customer's item and size is in stock and how many units are on hand.

### pricing
Fields: `sku` (TEXT, key), `unit_cost` (REAL), `list_price` (REAL)
Why it matters: gives the cost floor and the list price, so agents can quote orders and decide whether a discount still makes money.

### vendors
Fields: `id` (INTEGER, key), `name` (TEXT), `specialty` (TEXT), `lead_days` (INTEGER)
Why it matters: shows who can reprint or supply an item and how many days it takes, for restocking and delivery promises.

### leases
Fields: `id` (INTEGER, key), `space_name` (TEXT), `landlord` (TEXT), `monthly_rent` (REAL), `next_due` (TEXT), `notes` (TEXT)
Why it matters: holds the rent amount and due date that agents check before paying rent or answering a landlord.

### cash_accounts
Fields: `name` (TEXT, key), `balance` (REAL), `date` (TEXT)
Why it matters: the money available, which agents must check before approving any payment so the shop doesn't overspend.

### payments
Fields: `id` (INTEGER, key), `kind` (TEXT), `ref_id` (INTEGER), `amount` (REAL), `account` (TEXT), `paid_at` (TEXT), `approved_by` (TEXT)
Why it matters: the record of every payment an agent makes, including who approved it. It starts empty.

### invoices
Fields: `id` (INTEGER, key), `vendor_id` (INTEGER → vendors.id), `amount` (REAL), `due_date` (TEXT), `status` (TEXT), `description` (TEXT)
Why it matters: vendor bills the shop owes, which agents decide whether and when to pay.

### tickets
Fields: `id` (INTEGER, key), `type` (TEXT), `requester` (TEXT), `subject` (TEXT), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `lease_id` (INTEGER → leases.id), `invoice_id` (INTEGER → invoices.id), `status` (TEXT), `notes` (TEXT), `created_at` (TEXT)
Why it matters: the work queue. Each open ticket is a request (customer order, rent notice, price override) an agent has to resolve.

## MCP tools

Server: `mcp_server/server.py` (FastMCP), reading `data/campus_customs_new.db`. Every agent gets shop data only through these tools. Tools return only what's in the database and say "not found" when a row is missing.

### `check_inventory(sku, size)`
- **Reads:** `inventory`
- **Unlocks:** Ticket 101 — Tauhid Zaman wants 1 Classic Bulldog Tee (`CC-TEE-WHITE`) in size S
- **Why it fits:** Ticket 101 asks for one exact SKU and size, and this tool looks up exactly that (`sku`, `size`) row; it returns qty 0 for `CC-TEE-WHITE` S, so the agent knows the order can't be filled from the shelf.

### `get_lease(lease_id)`
- **Reads:** `leases`
- **Unlocks:** Ticket 102 — Elm City Properties' "Rent due" email, which references `lease_id` 1
- **Why it fits:** Ticket 102's email only says rent is due "in 2 days," so this tool pulls lease 1's actual terms from the database ($2,400.00 to Elm City Properties, due 2026-09-02) and the agent acts on the lease record, not the email's wording.

### `get_pricing(sku)`
- **Reads:** `pricing`
- **Unlocks:** Ticket 103 — Yale AI Club wants 20 `CC-HOOD-NAVY` hoodies (size M) at a bulk discount
- **Why it fits:** A bulk discount can only be judged against the price and the cost, and this tool returns `CC-HOOD-NAVY`'s $58.00 list price and $22.00 unit cost, so the agent can keep any discounted price above $22.00 per hoodie.

## Agent team (PydanticAI)

Code: `backend/team.py` (agents + loops), `backend/models.py` (data types), `backend/prompts/<role>.md` (one prompt per agent), `backend/audit.py`, `backend/run.py`. Run: `python -m backend.run [ticket ids]`.
Every agent uses `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`). Every agent can call `ask_agent(role, request)` to reach any other agent (full connectivity); only the Boss returns the final `TicketDecision`.

| Agent | Job | MCP tools it can use |
|---|---|---|
| Boss | Reads the ticket, delegates, makes the final call | `get_ticket`, `get_shop_date` |
| Inventory | Stock by SKU + size, shortfalls, which vendor restocks | `get_ticket`, `check_inventory`, `list_vendors`, `get_shop_date` |
| Accounting | Cash, invoices, margins; drafts payments and POs for human approval | `get_shop_date`, `get_cash_balance`, `get_invoice`, `find_payments`, `get_pricing`, `check_margin`, `prepare_payment`, `prepare_purchase_order` |
| Facilities | Leases, rent, utilities, the shop space | `get_lease`, `get_shop_date`, `find_payments` |
| Customer Service | Drafts customer messages; never sends | `get_ticket` |

## All MCP tools

| Tool | Table(s) | Added |
|---|---|---|
| `check_inventory(sku, size)` | inventory | P3 |
| `get_lease(lease_id)` | leases | P3 |
| `get_pricing(sku)` | pricing | P3 |
| `list_open_tickets()` | tickets | P5 |
| `list_tickets()` | tickets | P7 (backend `/tickets`) |
| `get_ticket(ticket_id)` | tickets | P5 |
| `get_shop_date()` | desk | P5 |
| `list_vendors()` | vendors | P5 |
| `get_cash_balance(account)` | cash_accounts | P5 |
| `get_invoice(invoice_id)` | invoices | P5 |
| `find_payments(kind, ref_id)` | payments | P5 |
| `check_margin(sku, unit_price, qty)` | pricing | P5 |
| `prepare_payment(kind, ref_id, amount, account)` | leases / invoices + vendors, cash_accounts, payments | P5 |
| `prepare_purchase_order(vendor_id, sku, size, qty)` | vendors, pricing, inventory, desk | P5 |

All tools are read-only. The two `prepare_*` tools return drafts marked `PENDING_HUMAN_APPROVAL` and write nothing.

## Backend API (FastAPI)

Start from `backend/`: `uvicorn main:app --reload --port 8000`. Base URL `http://localhost:8000`.

- `GET /tickets` — all tickets with status (open/resolved) and the Boss's latest decision.
- `POST /tickets/{ticket_id}/run` — runs the agent team on one ticket; returns the Boss's decision, token usage and any drafts awaiting approval.
- `GET /events?after={id}&ticket_id={id}&limit={n}` — recent agent events (agent, who called it, what it said, tools + args) for the board to poll.
- `GET /approvals?status=pending` — payment and purchase-order drafts the agents prepared.
- `POST /approvals/{approval_id}/approve` — a human approves a draft; re-checks the DB, records the payment and lowers cash (the only route that changes cash). Approvals and refusals are written to the audit trail.
- `GET /cash` — current `checking` balance from `cash_accounts`.
- `POST /reset` — restores `campus_customs_new.db` from the original and clears pending approvals; logs the starting checking balance (audit trail is kept).

## Dashboard (React + Vite + TypeScript)

`frontend/`, started with `npm run dev` at http://localhost:5173; talks to `http://localhost:8000` (`frontend/.env`), which allows that origin via CORS. Design notes: `output/design.md`.
- Lists the 3 tickets with chips: Open, Team working…, ✓ Resolved, and "N to approve".
- **Start the team** runs `POST /tickets/{id}/run`; while it runs, the board polls `GET /events` so the five blob agents talk in speech bubbles and the conversation feed fills in live.
- When the run finishes the ticket shows Resolved and **What each agent did** lists each agent's summary and MCP tools (agents that sat out are listed too, plus the run's token count).
- **Waiting for you** shows drafted pays/purchases with an **Approve** button (`POST /approvals/{id}/approve`); refusals (e.g. not enough cash) show as a message.
- The **Checking** pill shows `GET /cash`, and squishes with a "−$amount" badge when an approval lowers it.

## Full run and reports

- `python scripts/full_run.py` (backend + board running): resets the DB, runs each ticket on the board, clicks Approve on each draft, screenshots the board, then calls `finalize_run.py`.
- `python scripts/finalize_run.py`: from `output/audit_trail.json` (latest reset onward) and the working DB, fills each ticket's **Actual** section and the **Cash** tab in `output/desk_tickets.html`, and writes `output/resolved_tickets.json` and `output/resolved_board.html`.
- **Cash double check** (the script fails if any is off): starting balance − approved spending = `cash_accounts.checking`; approved spending = sum of `payments` rows (same count); the itemized running balance ends at the DB balance.

## Safety

Guardrails for real customers and real money:
- **Human approval for money and messages.** No tool can pay, order or send. Payments and POs are drafts; customer messages are drafts.
- **Pre-checks on every payment draft.** Amount must equal what's owed, fit in the cash balance, not already be paid (`find_payments`), and an invoice must be `open`.
- **No selling below cost.** Discounts go through `check_margin`; Accounting may not approve a price at or below `unit_cost`.
- **No invented data.** Facts come only from MCP tools on `campus_customs_new.db`; missing rows come back as "not found". The original DB is read-only and resettable.
- **Least privilege.** Each agent sees only the MCP tools its role needs.
- **Boss has the final word**, and every step is logged to `output/audit_trail.json` (append-only, atomic writes) with agent, caller, depth, tool calls, args, results and token usage.
- **Simulation only.** No real money moves and no emails are sent; there's no payment, bank or email code anywhere. "Paying" updates rows in the local SQLite working copy. Customer messages exist only as drafts.
- **Agents can't approve.** Approvals are written by `backend/approvals.py` on a human click, not by any MCP tool. Approve re-checks amount, cash and double payment in one transaction, re-prices POs from `pricing`, and refuses anything cash can't cover.
- **Reset is safe.** The original `campus_customs.db` is read-only; reset copies it over the working copy and logs it.

Limits that keep token use in check:
- One model (`gpt-6-luna`), `temperature=0`, `max_tokens=700` per reply.
- Per ticket, shared by the whole team: 20 model requests, 30 tool calls, 50,000 tokens. Hitting a limit stops that ticket and logs it.
- Delegation depth capped at 2 (Boss → agent → agent); at the cap, `ask_agent` is hidden from the agent entirely, and no agent can call back into its own chain (no loops).
- Short prompts, structured outputs, tool results kept small, delegates get only a short request (not the whole conversation), `retries=1`.
