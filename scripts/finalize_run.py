"""Build the run reports from the audit trail + working database (no model calls).

Fills, for the latest run after the last reset:
  output/desk_tickets.html  -> each ticket's Actual section + the Cash tab (with a double check)
  output/resolved_tickets.json
  output/resolved_board.html (board screenshots from output/screens/, embedded so it opens by double-click)
Exits non-zero if the cash double check fails.

Usage (from hw5/):  python scripts/finalize_run.py [--out DIR] [--audit FILE]
"""
import argparse
import base64
import html
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH  # noqa: E402

NAMES = {"boss": "Boss", "inventory": "Inventory", "accounting": "Accounting",
         "facilities": "Facilities", "customer_service": "Customer Service"}
SPECIALISTS = ["inventory", "accounting", "facilities", "customer_service"]
e = html.escape
money = lambda n: f"${n:,.2f}"  # noqa: E731


def summary_of(output: str | None) -> str | None:
    if not output:
        return None
    try:
        o = json.loads(output)
        return o.get("summary") or o.get("decision")
    except ValueError:
        m = re.search(r'"(?:summary|decision)":\s*"((?:[^"\\]|\\.)*)', output)
        return m.group(1) if m else None


def analyze_run(steps: list[dict]) -> dict:
    agents, delegations, tools, summaries = [], [], {}, {}
    for s in steps:
        a = s["agent"]
        if a not in agents:
            agents.append(a)
        for p in s.get("parts", []):
            if s["kind"] != "model_response" or p["kind"] != "tool-call" or p["tool"] == "final_result":
                continue
            if p["tool"] == "ask_agent":
                delegations.append({"from": a, "to": p["args"].get("role"), "request": p["args"].get("request")})
            else:
                tools.setdefault(a, []).append({"tool": p["tool"], "args": p["args"]})
        if s["kind"] == "end":
            summaries[a] = summary_of(s.get("output"))
    return {"agents": agents, "delegations": delegations, "tools": tools, "summaries": summaries}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--audit", default=str(ROOT / "output" / "audit_trail.json"))
    args = ap.parse_args()
    out = Path(args.out)
    trail = json.loads(Path(args.audit).read_text())

    resets = [i for i, x in enumerate(trail) if x["event"] == "reset"]
    if not resets:
        sys.exit("No reset found in the audit trail; run scripts/full_run.py first.")
    trail = trail[resets[-1]:]
    start = float(trail[0]["starting_checking_balance"])

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    end_balance = db.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    payments = [dict(r) for r in db.execute("SELECT * FROM payments ORDER BY id")]
    statuses = {r["id"]: r["status"] for r in db.execute("SELECT id, status FROM tickets")}

    approvals = [x for x in trail if x["event"] == "approval"]
    rejected = [x for x in trail if x["event"] == "approval_rejected"]

    tickets, actual_html = [], {}
    for tid in sorted(statuses):
        ends = [x for x in trail if x.get("ticket_id") == tid and x["event"] in ("ticket_end", "ticket_error")]
        last = ends[-1] if ends else None
        run_id = last["run_id"] if last else None
        steps = [x for x in trail if x["event"] == "step" and x.get("run_id") == run_id]
        r = analyze_run(steps)
        decision = (last or {}).get("decision", {})
        t_appr = [a for a in approvals if a["ticket_id"] == tid]
        contributions = {}
        for a in r["agents"]:
            contributions[a] = {
                "summary": decision.get("decision") if a == "boss" else r["summaries"].get(a),
                "delegated_to": [d["to"] for d in r["delegations"] if d["from"] == a],
                "tools": [t["tool"] for t in r["tools"].get(a, [])],
            }
        tickets.append({
            "id": tid,
            "final_status": statuses[tid],
            "boss_status": decision.get("status") or ("error" if last and last["event"] == "ticket_error" else None),
            "outcome": decision.get("decision") or (last or {}).get("error") or "Not run.",
            "run_id": run_id,
            "agents": contributions,
            "human_approvals": [{"approval_id": a["approval_id"], "type": a["type"], "amount": a["amount"],
                                 "approved_by": a["approved_by"], "what": a["draft"], "at": a["ts"]} for a in t_appr],
            "customer_message_draft": decision.get("customer_message_draft"),
            "usage": (last or {}).get("usage"),
        })

        # Actual section HTML
        if not last:
            body = "<p>This ticket was not run.</p>"
        else:
            pills = "".join(f'<span class="pill{"" if s in r["agents"] else " off"}">{NAMES[s]}</span>' for s in SPECIALISTS)
            dl = "".join(f'<li><strong>{NAMES[d["from"]]} → {NAMES.get(d["to"], d["to"])}:</strong> {e(str(d["request"]))}</li>'
                         for d in r["delegations"]) or "<li>No delegations.</li>"
            tl = "".join(
                f'<li><code>{e(t["tool"])}</code> — {NAMES[a]}'
                f'{" (" + e(", ".join(f"{k}={v}" for k, v in t["args"].items())) + ")" if t["args"] else ""}</li>'
                for a in r["agents"] for t in r["tools"].get(a, [])) or "<li>None.</li>"
            appr = "".join(f'<li>{e(a["type"].replace("_", " "))} of {money(a["amount"])} approved by {e(a["approved_by"])}</li>'
                           for a in t_appr) or "<li>None.</li>"
            u = last.get("usage") or {}
            body = f"""<h3>Boss's final call</h3>
    <p><strong>{e(str(decision.get("status", "error")).replace("_", " "))}:</strong> {e(tickets[-1]["outcome"])}</p>
    <h3>Agents that worked</h3>
    <span class="pill">Boss</span>{pills}
    <h3>Delegations</h3>
    <ol>{dl}</ol>
    <h3>MCP tools used</h3>
    <ul>{tl}</ul>
    <h3>Human approvals</h3>
    <ul>{appr}</ul>
    <p class="muted-note">Ticket status: {e(statuses[tid])} · run {e(str(run_id))} · {u.get("requests", 0)} model calls,
    {u.get("tool_calls", 0)} tool calls, {u.get("input_tokens", 0) + u.get("output_tokens", 0):,} tokens</p>"""
        actual_html[tid] = f'  <div class="card actual">\n    <h2>Actual</h2>\n    {body}\n  </div>'

    # --- cash: itemize + double check ---------------------------------------------------------
    rows, running = [], start
    for t in tickets:
        for a in t["human_approvals"]:
            running = round(running - a["amount"], 2)
            w = a["what"]
            what = (f'Paid {w.get("payee")} ({w.get("kind")} #{w.get("ref_id")})' if a["type"] == "payment"
                    else f'Purchase order: {w.get("qty")} × {w.get("sku")} {w.get("size")} from {w.get("vendor")}')
            rows.append((t["id"], what, -a["amount"], running))
        if not t["human_approvals"]:
            rows.append((t["id"], "No pay or purchase approved for this ticket", 0.0, running))
    total_out = round(sum(a["amount"] for a in approvals), 2)
    pay_total = round(sum(p["amount"] for p in payments), 2)
    checks = [
        ("Starting balance − approved spending = ending balance in cash_accounts",
         f"{money(start)} − {money(total_out)} = {money(start - total_out)} vs {money(end_balance)}",
         abs(start - total_out - end_balance) < 0.005),
        ("Approved spending = sum of rows in the payments table",
         f"{money(total_out)} vs {money(pay_total)} ({len(payments)} rows)",
         abs(total_out - pay_total) < 0.005 and len(payments) == len(approvals)),
        ("Running balance in this table ends at the database balance",
         f"{money(running)} vs {money(end_balance)}", abs(running - end_balance) < 0.005),
    ]
    ok = all(c[2] for c in checks)

    trs = "".join(f'<tr><td>#{tid}</td><td>{e(what)}</td><td class="num">{"−" + money(-amt) if amt else "$0.00"}</td>'
                  f'<td class="num">{money(bal)}</td></tr>' for tid, what, amt, bal in rows)
    rej = "".join(f'<li>Approval #{x["approval_id"]} refused: {e(x["reason"])}</li>' for x in rejected)
    chk = "".join(f'<li>{"✅" if c[2] else "❌"} {e(c[0])}<br><span class="muted-note">{e(c[1])}</span></li>' for c in checks)
    cash_html = f"""  <div class="card">
    <h2>Cash: checking account</h2>
    <table class="cash-table">
      <thead><tr><th>Ticket</th><th>What changed cash</th><th class="num">Amount</th><th class="num">Balance</th></tr></thead>
      <tbody>
        <tr class="edge"><td></td><td>Starting balance (after reset)</td><td></td><td class="num">{money(start)}</td></tr>
        {trs}
        <tr class="edge"><td></td><td>Ending balance (cash_accounts.checking)</td><td class="num">−{money(total_out)}</td><td class="num">{money(end_balance)}</td></tr>
      </tbody>
    </table>
    {"<h3>Refused approvals</h3><ul>" + rej + "</ul>" if rej else ""}
    <h3>Double check {"passed" if ok else "FAILED"}</h3>
    <ul class="checks">{chk}</ul>
  </div>"""

    # --- write desk_tickets.html ----------------------------------------------------------------
    desk = out / "desk_tickets.html"
    page = desk.read_text()
    for tid, block in actual_html.items():
        page = re.sub(rf"(<!--ACTUAL:{tid}-->).*?(<!--/ACTUAL:{tid}-->)", lambda m: f"{m[1]}\n{block}\n  {m[2]}", page, flags=re.S)
    page = re.sub(r"(<!--CASH-->).*?(<!--/CASH-->)", lambda m: f"{m[1]}\n{cash_html}\n  {m[2]}", page, flags=re.S)
    extra_css = (".actual{border-left:4px solid var(--accent)}.muted-note{color:var(--muted);font-size:13px}"
                 ".cash-table{width:100%;border-collapse:collapse;font-size:14px}.cash-table th,.cash-table td{padding:8px 6px;"
                 "border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.cash-table .num{text-align:right;"
                 "white-space:nowrap}.cash-table .edge td{font-weight:700}.checks{list-style:none;padding:0}.checks li{margin:8px 0}")
    if "/*RUN-CSS*/" not in page:
        page = page.replace("</style>", f"/*RUN-CSS*/{extra_css}\n</style>", 1)
    desk.write_text(page)

    # --- resolved_tickets.json ------------------------------------------------------------------
    (out / "resolved_tickets.json").write_text(json.dumps({
        "starting_checking_balance": start, "ending_checking_balance": end_balance,
        "cash_double_check_passed": ok, "tickets": tickets}, indent=2) + "\n")

    # --- resolved_board.html (screenshots embedded) ---------------------------------------------
    cards = []
    for t in tickets:
        shot = out / "screens" / f"ticket_{t['id']}.png"
        img = (f'<img alt="Board after ticket {t["id"]}" src="data:image/png;base64,{base64.b64encode(shot.read_bytes()).decode()}">'
               if shot.exists() else "<p><em>No screenshot found.</em></p>")
        cards.append(f'<section><h2>Ticket {t["id"]} · {e(t["final_status"])}</h2><p>{e(t["outcome"])}</p>{img}</section>')
    (out / "resolved_board.html").write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Resolved Board</title>
<style>:root{{--bg:#FFF8F1;--card:#fff;--ink:#2B2A33;--muted:#8A8794}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1E1C24;--card:#2A2731;--ink:#F4EFE9;--muted:#A9A3B3}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 ui-rounded,system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:28px 16px}}h1{{margin:0 0 4px}}.sub{{color:var(--muted);margin:0 0 20px}}
section{{background:var(--card);border-radius:24px;padding:20px;margin-bottom:22px;box-shadow:0 10px 30px -12px #8c5a282e}}
section h2{{margin:0 0 4px;font-size:18px}}section p{{margin:0 0 12px;color:var(--muted)}}
img{{width:100%;height:auto;border-radius:16px;display:block}}</style></head><body><main>
<h1>Campus Customs — Resolved Board</h1>
<p class="sub">Checking: {money(start)} → {money(end_balance)} · cash double check {"passed ✅" if ok else "FAILED ❌"}</p>
{"".join(cards)}</main></body></html>""")

    print(f"Start {money(start)} → end {money(end_balance)}; double check {'passed' if ok else 'FAILED'}")
    for c in checks:
        print(f"  {'OK ' if c[2] else 'BAD'} {c[0]}: {c[1]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
