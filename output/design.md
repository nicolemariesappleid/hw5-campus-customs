# Campus Customs Board — Design

Built with React + Vite + TypeScript in `frontend/`. It talks to the FastAPI backend at `http://localhost:8000` (set in `frontend/.env` as `VITE_API_URL`); the backend allows the Vite page origin (`http://localhost:5173`) through CORS.
Run: start the backend (`cd backend && uvicorn main:app --reload --port 8000`), then `cd frontend && npm install && npm run dev` and open http://localhost:5173.

Preview (scripted demo run of ticket 102): `output/board_preview.png`

## The look I chose: calm, soft, a little playful

Modeled on the feel of Headspace: a warm cream background, one sunny orange accent, pastel color for everything else, rounded "Nunito" type, big soft corners (20–28px), gentle shadows instead of hard borders, and springy "squish" animations. **Why:** an agent team spending money can feel tense. A calm, friendly board makes it easy to watch the agents work and make one clear decision (approve or don't) without feeling rushed.

## Layout

- **Top bar:** a time-of-day greeting on the left; the **checking balance** in a pill on the right, always visible.
- **Left column:** the three **ticket cards** plus a dashed "Reset shop to original" button at the bottom (low-key so it isn't clicked by accident).
- **Main area, top to bottom:**
  1. **Ticket hero:** type, number, subject, requester, and one big orange **Start the team** button.
  2. **The stage:** all five agents standing in a row on a soft peach gradient, with speech bubbles above them.
  3. **Conversation** (left): a chat-style feed of every step, in order.
  4. **Side panels** (right): **Waiting for you** (approvals) and **What each agent did** (summary).

**Why:** it reads top-to-bottom like the work happens: pick a ticket → start → watch → decide → review. The stage is the "live" view; the conversation is the full record.

## How the agents read differently

Each agent is an original, bubbly blob character with its own **color, body shape and tiny prop**, so you can tell them apart without reading:

| Agent | Color | Prop |
|---|---|---|
| Boss | orange | little crown |
| Inventory | blue | cardboard box |
| Accounting | green | gold coin |
| Facilities | purple | key |
| Customer Care | pink | heart |

They act out what's happening:
- **Talking** (the agent working right now): bounces, mouth moving, with a **speech bubble** showing what it said or a friendly line for the tool it's using ("Checking the shelves", "Pulling up the lease", "Drafting a payment for you").
- **Idle** (has helped this run): eyes open, gently breathing, blinking.
- **Asleep** (not used on this ticket): eyes closed, faded colors. That makes it obvious that not every specialist works every ticket.
- **Done** (run finished): smiling. The Boss's bubble shows its final call.

In the conversation feed each message uses the agent's pastel color and says who asked it ("Facilities · asked by Boss"), so delegation between agents is visible.

**Why:** colors and props give each role a personality that sticks, and moods turn an audit log into something you can follow at a glance.

## How resolved tickets show up

- Ticket cards show a chip: grey **Open**, pulsing orange **Team working…** during a run, then a green **✓ Resolved** chip with a soft mint wash over the whole card when the run finishes.
- A pink **"N to approve"** chip stays on the card if the run left a payment or purchase waiting for you.
- After the run, **What each agent did** lists only the agents that worked: a one-line summary, the MCP tools they used as small tags, then "Sat this one out" for the rest and the run's token count.

**Why:** green = done and pink = needs you are easy to spot from the list without opening a ticket. Showing tokens keeps cost visible.

## How cash shows up

- The **Checking** pill shows the live balance from `GET /cash` and its as-of date, in calm green.
- Approvals sit in a **Waiting for you** card with a pink outline: who gets paid, what for, the amount, and a green **Approve** button. A note says it's a simulated shop.
- When you approve, the balance updates. The pill **squishes**, the number turns orange, and a pink **−$2,400.00** badge pops in for a few seconds.

**Why:** money only moves on a human click, so that moment gets the clearest feedback on the page. You see exactly what changed and by how much.

## Accessibility and comfort

Light and dark mode follow the system; motion turns off for anyone with "reduce motion" set; text sits on light pastel backgrounds for contrast; the layout stacks to one column on narrow screens.
