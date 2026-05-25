"""
Pydantic v2 models for the Slack-notifier service.

Field names match INTERFACE-CONTRACT.md §4 exactly (snake_case throughout).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models — OpsNotification v1  (INTERFACE-CONTRACT §4.5 + DESIGN-REVIEW §6.6 / Appendix C)
# ---------------------------------------------------------------------------

class AffectedComponent(BaseModel):
    type: str
    name: str
    project: str
    region: Optional[str] = None


class RecommendedAction(BaseModel):
    id: str
    label: str
    action_class: str
    tier: int = Field(ge=0, le=4)
    estimated_duration_s: Optional[int] = None
    reversible: bool


class References(BaseModel):
    logs: Optional[str] = None
    dashboard: Optional[str] = None
    trace: Optional[str] = None
    runbook: Optional[str] = None
    scc: Optional[str] = None
    ticket: Optional[str] = None
    workflow: Optional[str] = None


class AgentMeta(BaseModel):
    identity: str
    model: str
    tokens: Optional[dict] = None   # {"in": int, "out": int}
    trace_id: Optional[str] = None


class OpsNotification(BaseModel):
    schema_: str = Field(alias="schema", default="ops.notification.v1")
    notification_id: str
    correlation_id: str
    produced_at: datetime
    severity: str   # info|low|medium|high|critical
    environment: str  # dev|prod
    domain: str  # sre|devsecops|platform|finops|orchestrator

    summary: str = Field(min_length=20, max_length=400)
    affected_component: AffectedComponent
    impact: str = Field(min_length=20)
    likely_cause: Optional[str] = None

    recommended_actions: List[RecommendedAction] = Field(min_length=1)
    human_required: bool
    approval_window_until: Optional[datetime] = None
    references: References
    agent: AgentMeta

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# ActionApproval v1  (INTERFACE-CONTRACT §4.4)
# ---------------------------------------------------------------------------

class ActionApproval(BaseModel):
    action_id: str
    approval_id: str
    decision: str   # approved|rejected|expired
    approver_identity: List[str]
    approved_at: datetime
