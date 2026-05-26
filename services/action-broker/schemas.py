"""
Pydantic v2 models for the Action Broker service.

All field names match `agents/aop_common/schemas.py` (snake_case throughout).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Sub-models shared across schemas
# ---------------------------------------------------------------------------


class ActionTarget(BaseModel):
    type: str
    name: str
    project: str
    region: str | None = None


class ModelMeta(BaseModel):
    id: str
    tokens_in: int = 0
    tokens_out: int = 0


class PolicyDecision(BaseModel):
    tier: int
    rule: str
    outcome: str  # approved|denied|expired


# ---------------------------------------------------------------------------
# ActionRequest v1
# ---------------------------------------------------------------------------


class ActionRequest(BaseModel):
    action_id: str
    recommendation: dict[str, Any]  # Recommendation v1 — kept as dict to avoid circular dep
    requested_by: str  # agent identity
    idempotency_key: str
    approval_window_until: datetime | None = None


# ---------------------------------------------------------------------------
# ActionApproval v1
# ---------------------------------------------------------------------------


class ActionApproval(BaseModel):
    action_id: str
    approval_id: str
    decision: str  # approved|rejected|expired
    approver_identity: list[str]
    approved_at: datetime


# ---------------------------------------------------------------------------
# ActionExecuted v1
# ---------------------------------------------------------------------------


class ExecutionOutcome(BaseModel):
    status: str  # success|failed|rolled_back
    detail: str | None = None
    resource_refs: list[str] = Field(default_factory=list)


class ActionExecuted(BaseModel):
    action_id: str
    status: str  # success|failed|rolled_back
    outcome: ExecutionOutcome
    verification: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# AuditRecord v1
# ---------------------------------------------------------------------------


class AuditRecord(BaseModel):
    audit_id: str
    correlation_id: str
    timestamp: datetime
    phase: str  # signal|finding|recommendation|action_requested|action_approved|action_executed|rollback
    agent_identity: str
    human_identity: str | None = None
    environment: str
    domain: str
    action_class: str | None = None
    policy_decision: PolicyDecision
    evidence_refs: list[str] = Field(default_factory=list)
    model: ModelMeta | None = None
    outcome: dict[str, Any] | None = None
