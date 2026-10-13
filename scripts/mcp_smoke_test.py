"""Smoke test the campus-customs MCP server through a real MCP (stdio) connection.

Launches the server exactly as .mcp.json describes, calls each tool, then reads
data/campus_customs_new.db directly and checks every returned value matches.
Writes the evidence to output/mcp_smoke.json.

Usage (from the hw5 folder):  python scripts/mcp_smoke_test.py
"""
import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DB_PATH  # noqa: E402

PROMPT = (
    "this is problem 4. add your mcp server in this vibecoder to this project so the vibe "
    "coder can call the tools. save the connection JSON text in .mcp.json at the project root "
    "or however you save local mcp server lists. with you connected, test each of your 3 mcp "
    "tools. save the evidence in output/mcp_smoke.json . for every tool include the prompt i "
    "asked the vibe coder, the tool name, and the tool output, which must match values in "
    "data/campus_customs_new.db"
)

# (tool, arguments, ticket, SQL that returns the same row straight from the database)
TESTS = [
    ("check_inventory", {"sku": "CC-TEE-WHITE", "size": "S"}, 101,
     "SELECT sku, name, size, qty, location FROM inventory WHERE sku=? AND size=?",
     ("CC-TEE-WHITE", "S")),
    ("get_lease", {"lease_id": 1}, 102,
     "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id=?",
     (1,)),
    ("get_pricing", {"sku": "CC-HOOD-NAVY"}, 103,
     "SELECT sku, unit_cost, list_price FROM pricing WHERE sku=?",
     ("CC-HOOD-NAVY",)),
]


async def main() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text())
    server = config["mcpServers"]["campus-customs"]
    server = {**server, "cwd": str(ROOT)}

    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    results = []
    async with Client({"mcpServers": {"campus-customs": server}}) as client:
        tools = [t.name for t in await client.list_tools()]
        for tool, args, ticket, sql, params in TESTS:
            output = (await client.call_tool(tool, args)).data
            db_row = dict(db.execute(sql, params).fetchone())
            output_fields = {k: v for k, v in output.items() if k != "found"}
            results.append({
                "ticket": ticket,
                "prompt": PROMPT,
                "tool_name": tool,
                "arguments": args,
                "tool_output": output,
                "database_row": db_row,
                "matches_database": output.get("found") is True and output_fields == db_row,
            })

    evidence = {
        "server": "campus-customs",
        "connection": ".mcp.json (stdio: " + " ".join([server["command"], *server["args"]]) + ")",
        "database": str(DB_PATH.relative_to(ROOT)),
        "tools_listed_by_server": tools,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "all_match": all(r["matches_database"] for r in results),
        "tests": results,
    }
    out = ROOT / "output" / "mcp_smoke.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
