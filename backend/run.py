"""Run the Campus Customs team on tickets from the command line.

Usage (from the hw5 folder):
    python -m backend.run            # every open ticket
    python -m backend.run 101 103    # just these tickets
"""
import asyncio
import json
import os
import sys

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from backend.team import build_team, mcp, run_ticket  # noqa: E402


async def main(ticket_ids: list[int]) -> None:
    team = build_team()
    async with mcp:  # one MCP server process for the whole run
        if not ticket_ids:
            ticket_ids = [t["id"] for t in await mcp.direct_call_tool("list_open_tickets", {})]
        for tid in ticket_ids:
            print(json.dumps(await run_ticket(team, tid), indent=2))


if __name__ == "__main__":
    asyncio.run(main([int(a) for a in sys.argv[1:]]))
