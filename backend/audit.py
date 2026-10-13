"""Append-only audit trail at output/audit_trail.json (a JSON array; never wiped)."""
import json
import os
from datetime import datetime, timezone
from typing import Any

from pydantic_ai import Agent

from backend.models import TeamDeps
from config import PROJECT_DIR

AUDIT_PATH = PROJECT_DIR / "output" / "audit_trail.json"
CLIP = 400  # max characters kept per text field, so the trail stays readable


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= CLIP else text[:CLIP] + "…"


def append(entry: dict) -> None:
    """Add one entry to the trail, keeping every earlier entry."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    trail = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size else []
    trail.append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry})
    tmp = AUDIT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(trail, indent=1, default=str))
    os.replace(tmp, AUDIT_PATH)  # atomic: a crash never leaves a half-written file


def _parts(parts) -> list[dict]:
    out = []
    for p in parts:
        kind = p.part_kind
        if kind in ("system-prompt", "instruction"):
            continue  # prompts live in backend/prompts/; no need to repeat them every step
        item = {"kind": kind}
        if hasattr(p, "tool_name"):
            item["tool"] = p.tool_name
        if kind == "tool-call":
            item["args"] = p.args_as_dict()
        elif hasattr(p, "content"):
            item["content"] = _clip(p.content)
        out.append(item)
    return out


def log_step(deps: TeamDeps, role: str, step: int, node, usage) -> None:
    """Record one agent-loop step: who, where in the delegation chain, what happened, tokens so far."""
    if Agent.is_user_prompt_node(node):
        kind, detail = "user_prompt", {"prompt": _clip(node.user_prompt)}
    elif Agent.is_model_request_node(node):
        kind, detail = "model_request", {"parts": _parts(node.request.parts)}
    elif Agent.is_call_tools_node(node):
        r = node.model_response
        kind, detail = "model_response", {"model": r.model_name, "parts": _parts(r.parts),
                                          "tokens": {"in": r.usage.input_tokens, "out": r.usage.output_tokens}}
    elif Agent.is_end_node(node):
        kind, detail = "end", {"output": _clip(node.data.output.model_dump(exclude_none=True))}
    else:
        kind, detail = type(node).__name__, {}
    append({"event": "step", "run_id": deps.run_id, "ticket_id": deps.ticket_id, "agent": role,
            "depth": deps.depth, "called_by": deps.chain[-1] if deps.chain else None,
            "step": step, "kind": kind, **detail,
            "team_usage": {"requests": usage.requests, "tool_calls": usage.tool_calls,
                           "tokens": usage.input_tokens + usage.output_tokens}})
