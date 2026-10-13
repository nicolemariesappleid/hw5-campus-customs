"""The Campus Customs agent team (PydanticAI): Boss, Inventory, Accounting, Facilities, Customer Service.

- Every agent uses gpt-6-luna through Portkey (config.portkey_model).
- Shop facts come only from the campus-customs MCP server; each agent sees just the MCP tools its role needs.
- Any agent can ask any other agent for help (ask_agent). The Boss makes the final call.
- Every agent-loop step is appended to output/audit_trail.json.
"""
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RunUsage, UsageLimits

from datetime import datetime, timezone

from backend import approvals, audit
from backend.models import AgentReport, Role, TeamDeps, TicketDecision
from config import PROJECT_DIR, portkey_model

ROLES: tuple[Role, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")
PROMPTS = PROJECT_DIR / "backend" / "prompts"

# MCP tools each role can see (fewer tool schemas = fewer tokens per request).
TOOLS: dict[str, set[str]] = {
    "boss": {"get_ticket", "get_shop_date"},
    "inventory": {"get_ticket", "check_inventory", "list_vendors", "get_shop_date"},
    "accounting": {"get_shop_date", "get_cash_balance", "get_invoice", "find_payments",
                   "get_pricing", "check_margin", "prepare_payment", "prepare_purchase_order"},
    "facilities": {"get_lease", "get_shop_date", "find_payments"},
    "customer_service": {"get_ticket"},
}

# Token guardrails
MAX_DEPTH = 2  # Boss -> agent -> agent, no deeper
LIMITS = UsageLimits(request_limit=20, tool_calls_limit=30, total_tokens_limit=50_000)  # per ticket, whole team
SETTINGS = ModelSettings(temperature=0, max_tokens=700)

# One MCP connection shared by all agents.
mcp = MCPToolset(PROJECT_DIR / "mcp_server" / "server.py")


async def run_agent(team: dict[str, Agent], role: str, prompt: str, deps: TeamDeps,
                    usage: RunUsage) -> AgentReport | TicketDecision:
    """Run one agent's loop, logging every step. `usage` is shared so limits cover the whole team."""
    async with team[role].iter(prompt, deps=deps, usage=usage, usage_limits=LIMITS) as run:
        step = 0
        async for node in run:
            step += 1
            audit.log_step(deps, role, step, node, run.usage)
            if Agent.is_model_request_node(node):  # queue prepare_* drafts for human approval
                for p in node.request.parts:
                    if p.part_kind == "tool-return":
                        approvals.capture(deps.run_id, deps.ticket_id, p.tool_name, p.content)
    return run.result.output


async def run_ticket(team: dict[str, Agent], ticket_id: int) -> dict:
    """Run the whole team on one ticket (Boss first). Needs `mcp` to be open."""
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-t{ticket_id}"
    usage = RunUsage()
    audit.append({"event": "ticket_start", "run_id": run_id, "ticket_id": ticket_id,
                  "limits": {"requests": LIMITS.request_limit, "tool_calls": LIMITS.tool_calls_limit,
                             "tokens": LIMITS.total_tokens_limit}})
    used = lambda: {"requests": usage.requests, "tool_calls": usage.tool_calls,  # noqa: E731
                    "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    try:
        decision = await run_agent(team, "boss", f"Resolve ticket {ticket_id}.", TeamDeps(run_id, ticket_id), usage)
    except Exception as e:  # includes UsageLimitExceeded: stop this ticket, log it
        error = f"{type(e).__name__}: {e}"
        audit.append({"event": "ticket_error", "run_id": run_id, "ticket_id": ticket_id, "error": error, "usage": used()})
        return {"run_id": run_id, "ticket_id": ticket_id, "error": error, "usage": used()}
    out = decision.model_dump(exclude_none=True)
    approvals.record_decision(ticket_id, out)
    audit.append({"event": "ticket_end", "run_id": run_id, "ticket_id": ticket_id, "decision": out, "usage": used()})
    return {"run_id": run_id, "ticket_id": ticket_id, "decision": out, "usage": used()}


def _add_ask_agent(team: dict[str, Agent], me: str) -> None:
    others = [r for r in ROLES if r != me]

    async def hide_when_too_deep(ctx: RunContext[TeamDeps], tool_def: ToolDefinition):
        return tool_def if ctx.deps.depth < MAX_DEPTH else None

    async def ask_agent(ctx: RunContext[TeamDeps], role: Role, request: str) -> str:
        if role == me or role not in team:
            return f"Choose one of: {', '.join(others)}."
        if role in ctx.deps.chain:
            return f"{role} is already waiting on you in this chain; answer with what you have."
        child = TeamDeps(ctx.deps.run_id, ctx.deps.ticket_id, ctx.deps.depth + 1, ctx.deps.chain + [me])
        result = await run_agent(team, role, request, child, ctx.usage)
        return result.model_dump_json(exclude_none=True)

    ask_agent.__doc__ = (f"Ask another Campus Customs agent ({', '.join(others)}) to do a task or answer a "
                         "question. Keep the request short and include facts it needs.")
    team[me].tool(prepare=hide_when_too_deep)(ask_agent)


def build_team() -> dict[str, Agent]:
    model = portkey_model()  # gpt-6-luna via Portkey, for every agent
    team = {
        role: Agent(
            model,
            name=role,
            deps_type=TeamDeps,
            output_type=TicketDecision if role == "boss" else AgentReport,
            instructions=(PROMPTS / f"{role}.md").read_text(),
            toolsets=[mcp.filtered(lambda ctx, td, allowed=TOOLS[role]: td.name in allowed)],
            model_settings=SETTINGS,
            retries=1,
        )
        for role in ROLES
    }
    for role in ROLES:
        _add_ask_agent(team, role)
    return team
