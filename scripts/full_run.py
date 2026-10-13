"""Full run of all open tickets ON THE BOARD, then build the reports.

Needs, in other terminals:
  1. backend:  cd backend && uvicorn main:app --reload --port 8000   (PORTKEY_API_KEY set)
  2. board:    cd frontend && npm run dev                            (http://localhost:5173)
One-time:    pip install playwright && python -m playwright install chromium

Then from hw5/:  python scripts/full_run.py
It resets the working DB, then for each ticket: picks it on the board, clicks "Start the team",
waits for the run to finish, clicks Approve on each drafted pay/purchase (this is the human
approval you authorized), and screenshots the board. Finally it runs finalize_run.py.
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
API, BOARD = "http://localhost:8000", "http://localhost:5173"
RUN_TIMEOUT_MS = 10 * 60 * 1000


def api(path: str, method: str = "GET"):
    req = urllib.request.Request(API + path, method=method)
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--audit", default=str(ROOT / "output" / "audit_trail.json"))
    args = ap.parse_args()
    shots = Path(args.out) / "screens"
    api("/reset", "POST")
    start = api("/cash")
    print(f"Reset done. Starting checking balance: ${start['balance']:,.2f}")
    ticket_ids = [t["id"] for t in api("/tickets")]
    shots.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(BOARD)
        page.wait_for_selector(".ticket")
        for tid in ticket_ids:
            print(f"Ticket {tid}: running the team…")
            page.locator(".ticket", has_text=f"#{tid}").click()
            page.click("button.go")
            page.wait_for_function("() => document.querySelector('button.go').disabled", timeout=10_000)
            page.wait_for_function("() => !document.querySelector('button.go').disabled", timeout=RUN_TIMEOUT_MS)
            page.wait_for_timeout(1500)

            skipped = 0  # approvals the backend refused (e.g. not enough cash) stay on screen
            while page.locator("button.approve").count() > skipped:
                before = page.locator("button.approve").count()
                page.locator("button.approve").nth(skipped).click()
                page.wait_for_timeout(1500)
                if page.locator("button.approve").count() == before:
                    print(f"  approval refused: {page.locator('.toast').inner_text() if page.locator('.toast').count() else '?'}")
                    skipped += 1
                else:
                    print(f"  approved; checking now {page.inner_text('.cash-amount')}")
            page.wait_for_timeout(1000)
            page.screenshot(path=str(shots / f"ticket_{tid}.png"), full_page=True)
            status = next(t for t in api("/tickets") if t["id"] == tid)["status"]
            print(f"  ticket {tid} is {status}")
        browser.close()

    sys.exit(subprocess.call([sys.executable, str(ROOT / "scripts" / "finalize_run.py"),
                              "--out", args.out, "--audit", args.audit]))


if __name__ == "__main__":
    main()
