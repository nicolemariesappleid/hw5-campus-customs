"""Data types shared by the Campus Customs agent team."""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]


@dataclass
class TeamDeps:
    """Passed to every agent run. Tracks who called whom for delegation and the audit trail."""
    run_id: str
    ticket_id: int | None
    depth: int = 0                      # 0 = Boss on the ticket; each delegation adds 1
    chain: list[str] = field(default_factory=list)  # roles on the current call path


class AgentReport(BaseModel):
    """What a specialist (non-Boss) agent returns."""
    summary: str = Field(description="1-2 sentences.")
    facts: list[str] = Field(default_factory=list, description="Facts from tools, each with its value.")
    recommendation: str
    approvals_needed: list[str] = Field(default_factory=list, description="Payments, POs, discounts or messages a human must approve.")
    customer_message_draft: str | None = Field(default=None, description="Draft only; never sent.")


class TicketDecision(BaseModel):
    """The Boss's final call on a ticket."""
    ticket_id: int
    status: Literal["resolved", "needs_human_approval", "blocked"]
    decision: str = Field(description="The final call, 1-3 sentences.")
    agents_used: list[Role] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    approvals_needed: list[str] = Field(default_factory=list)
    customer_message_draft: str | None = None
