"""
Pydantic v2 models for the Action Broker service.

All field names match INTERFACE-CONTRACT.md §4 exactly (snake_case).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models shared across schemas
# ---------------------------------------------------------------------------

class ActionTarget(BaseModel):
    type: str
    name: str
    project: str
    region: Optional[str] = None


class ModelMeta(BaseModel):
    id: str
    tokens_in: int = 0
    tokens_out: int = 0


class PolicyDecision(BaseModel):
    tier: int
    rule: str
    outcome: str   # approved|denied|expired


# ---------------------------------------------------------------------------
# ActionRequest v1  (INTERFACE-CONTRACT §4.4)
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    action_id: str
    recommendation: Dict[str, Any]   # Recommendation v1 — kept as dict to avoid circular dep
    requested_by: str                # agent identity
    idempotency_key: str
    approval_window_until: Optional[datetime] = None


# ---------------------------------------------------------------------------
# ActionApproval v1  (INTERFACE-CONTRACT §4.4)
# ---------------------------------------------------------------------------

class ActionApproval(BaseModel):
    action_id: str
    approval_id: str
    decision: str   # approved|rejected|expired
    approver_identity: List[str]
    approved_at: datetime


# ---------------------------------------------------------------------------
# ActionExecuted v1  (INTERFACE-CONTRACT §4.4)
# ---------------------------------------------------------------------------

class ExecutionOutcome(BaseModel):
    status: str        # success|failed|rolled_back
    detail: Optional[str] = None
    resource_refs: List[str] = Field(default_factory=list)


class ActionExecuted(BaseModel):
    action_id: str
    status: str        # success|failed|rolled_back
    outcome: ExecutionOutcome
    verification: Dict[str, Any] = Field(default_factory=dict)
    rollback: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# AuditRecord v1  (INTERFACE-CONTRACT §4.6)
# ---------------------------------------------------------------------------

class AuditRecord(BaseModel):
    audit_id: str
    correlation_id: str
    timestamp: datetime
    phase: str   # signal|finding|recommendation|action_requested|action_approved|action_executed|rollback
    agent_identity: str
    human_identity: Optional[str] = None
    environment: str
    domain: str
    action_class: Optional[str] = None
    policy_decision: PolicyDecision
    evidence_refs: List[str] = Field(default_factory=list)
    model: Optional[ModelMeta] = None
    outcome: Optional[Dict[str, Any]] = None
