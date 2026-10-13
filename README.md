# Campus Customs — HW5 Agent Desk

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works Campus Customs' open desk tickets. It's built with **PydanticAI**, gets every shop fact from a **FastMCP** server over SQLite, is served by a **FastAPI** backend, and runs on a **React + Vite + TypeScript** board. Every agent uses **`gpt-6-luna` through Portkey** only.

> **Simulation only.** The shop is fake. No real money moves and no emails are sent. Agents only read data and *prepare* drafts; a human clicking **Approve** is the only thing that changes cash, and it only updates the local SQLite working copy.

## Layout

```
hw5/
├── AI_prompts.md            prompt log, problems 1–11
├── requirements.txt         Python packages
├── .env.example             copy to .env and add PORTKEY_API_KEY (never commit .env)
├── .mcp.json                registers the MCP server for the vibe coder
├── config.py                one place for DB path + Portkey/gpt-6-luna model
├── data/
│   ├── campus_customs.db       ORIGINAL (read-only, used for resets)
│   └── campus_customs_new.db   WORKING COPY (agents + backend use this)
├── mcp_server/              FastMCP server: 14 tools over the working copy
├── backend/                 FastAPI app (main.py), agents (team.py), data types (models.py),
│   └── prompts/             one prompt per agent
├── frontend/                React + Vite + TypeScript board
├── scripts/                 reset_db.py, mcp_smoke_test.py, full_run.py, finalize_run.py
└── output/                  harness.md, mcp_smoke.json, desk_tickets.html, design.md,
                             resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt
```

## One-time setup

```bash
cd hw5
cp .env.example .env                 # then put your real PORTKEY_API_KEY in .env
pip install -r requirements.txt
python -m playwright install chromium   # only needed for scripts/full_run.py
cd frontend && npm install && cd ..
```

## 1. Copy the original DB to the working copy (clean run)

The original `data/campus_customs.db` is never changed. To start clean, copy it over the working copy:

```bash
python scripts/reset_db.py
# same thing by hand:  cp data/campus_customs.db data/campus_customs_new.db
```

## 2. Start the MCP server

```bash
python mcp_server/server.py
```

It talks over stdio and reads `data/campus_customs_new.db`. You only need to start it by hand to test it. The backend starts its own copy automatically, and the vibe coder starts it from `.mcp.json`. To check all tools against the database:

```bash
python scripts/mcp_smoke_test.py      # writes output/mcp_smoke.json
```

## 3. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Routes: `GET /tickets`, `POST /tickets/{id}/run`, `GET /events`, `GET /approvals`, `POST /approvals/{id}/approve`, `GET /cash`, `POST /reset`. See `output/harness.md`.

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev                          # open http://localhost:5173
```

The board calls the backend at `http://localhost:8000` (set in `frontend/.env`). The backend allows the Vite page origin through CORS.

## 5. Reset the DB before a full 3-ticket run

Always reset first so the run starts from the original $3,400.00 checking balance. Any of these works:

- click **Reset shop to original** on the board, or
- `curl -X POST http://localhost:8000/reset` (also logs the starting balance to the audit trail), or
- stop the backend and run `python scripts/reset_db.py`.

Then run all three tickets, either by clicking **Start the team** and **Approve** on the board for 101, 102 and 103, or automatically with the backend and board running:

```bash
python scripts/full_run.py
```

`full_run.py` resets the database, runs each ticket on the board, approves the drafted payments and purchases, screenshots the board, and then runs `scripts/finalize_run.py`. That fills in the Actual sections and Cash tab of `output/desk_tickets.html` (with a cash double check) and writes `output/resolved_tickets.json` and `output/resolved_board.html`. Every agent step is appended to `output/audit_trail.json`.

## Safety and token limits (short version)

- Agents get data only from MCP tools; payment and PO tools only make drafts marked `PENDING_HUMAN_APPROVAL`.
- Approval re-checks the amount, cash and double payment in one transaction, and refuses anything cash can't cover.
- Each agent sees only its own tools. Delegation is capped at two levels, and each ticket is capped at 20 model calls, 30 tool calls and 50k tokens.
- Full details are in `output/harness.md`.
