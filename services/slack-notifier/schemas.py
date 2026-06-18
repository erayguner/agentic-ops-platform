"""
Pydantic v2 models for the Slack-notifier service.

Field names match `agents/aop_common/schemas.py` (snake_case throughout).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Sub-models — OpsNotification v1 (DESIGN-REVIEW §6.6 / Appendix C)
# ---------------------------------------------------------------------------


class AffectedComponent(BaseModel):
    type: str
    name: str
    project: str
    region: str | None = None


class RecommendedAction(BaseModel):
    id: str
    label: str
    action_class: str
    tier: int = Field(ge=0, le=4)
    estimated_duration_s: int | None = None
    reversible: bool


class References(BaseModel):
    logs: str | None = None
    dashboard: str | None = None
    trace: str | None = None
    runbook: str | None = None
    scc: str | None = None
    ticket: str | None = None
    workflow: str | None = None


class AgentMeta(BaseModel):
    identity: str
    model: str
    tokens: dict | None = None  # {"in": int, "out": int}
    trace_id: str | None = None


class OpsNotification(BaseModel):
    schema_: str = Field(alias="schema", default="ops.notification.v1")
    notification_id: str
    correlation_id: str
    produced_at: datetime
    severity: str  # info|low|medium|high|critical
    environment: str  # dev|prod
    domain: str  # sre|devsecops|platform|finops|decommission|orchestrator

    summary: str = Field(min_length=20, max_length=400)
    affected_component: AffectedComponent
    impact: str = Field(min_length=20)
    likely_cause: str | None = None

    recommended_actions: list[RecommendedAction] = Field(min_length=1)
    human_required: bool
    approval_window_until: datetime | None = None
    references: References
    agent: AgentMeta

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# ActionApproval v1
# ---------------------------------------------------------------------------


class ActionApproval(BaseModel):
    action_id: str
    approval_id: str
    decision: str  # approved|rejected|expired
    approver_identity: list[str]
    approved_at: datetime
