"""aop_common.schemas — Pydantic v2 models for every AOP schema.

Snake_case throughout; default factories supply ids and timestamps automatically.
All models use model_config = ConfigDict(strict=True, populate_by_name=True).
These models are the source of truth for cross-component field names; the
matching schemas in `services/slack-notifier/` and `services/action-broker/`
must stay in lock-step.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Shared config dict applied to every model.
_CFG = ConfigDict(strict=True, populate_by_name=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now_rfc3339() -> str:
    return datetime.now(UTC).isoformat()


def _signal_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"sig_{ts}_{uuid.uuid4().hex[:8]}"


def _prefixed_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- #
# 4.1 OpsSignal v1
# --------------------------------------------------------------------------- #


class OpsSignal(BaseModel):
    """Normalised operational signal — published to ops.signals."""

    model_config = _CFG

    schema_: Literal["ops.signal.v1"] = Field("ops.signal.v1", alias="schema")
    signal_id: str = Field(default_factory=_signal_id)
    correlation_id: str = Field(
        default_factory=lambda: _prefixed_id("inc_"),
        description="Incident or correlation id — inherits from source or new.",
    )
    produced_at: str = Field(default_factory=_now_rfc3339)
    source: str = Field(
        ...,
        description=(
            "Origin of the signal. One of: monitoring, scc, audit, deploy, "
            "scheduler, agent_self, or a free-form service name."
        ),
    )
    source_ref: str = Field(..., description="URN or URI identifying the source record.")
    environment: Literal["dev", "prod"]
    severity: Literal["info", "low", "medium", "high", "critical"]
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque source payload. Validated downstream by the specialist agent.",
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Contextual labels: service, project, region, etc.",
    )


# --------------------------------------------------------------------------- #
# 4.3 Recommendation v1 (referenced by Finding)
# --------------------------------------------------------------------------- #


class RecommendationTarget(BaseModel):
    """Resource target for an action recommendation."""

    model_config = _CFG

    type: str
    name: str
    project: str
    region: str = "europe-west2"


class Recommendation(BaseModel):
    """A single typed action recommendation — part of a Finding."""

    model_config = _CFG

    schema_: Literal["ops.recommendation.v1"] = Field("ops.recommendation.v1", alias="schema")
    recommendation_id: str = Field(default_factory=lambda: _prefixed_id("rec_"))
    action_class: str = Field(
        ...,
        description=(
            "Canonical action class string (see "
            "services/action-broker/policy/action_classes.yaml). "
            "Examples: cloud_run.rollback_to_previous, iam.disable_service_account_key"
        ),
    )
    target: RecommendationTarget
    params: dict[str, Any] = Field(default_factory=dict)
    proposed_tier: int = Field(
        ...,
        ge=0,
        le=4,
        description="Autonomy tier the agent proposes. Final tier is set by the policy engine.",
    )
    estimated_duration_s: int = Field(0, ge=0)
    reversible: bool = True
    rationale: str = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# 4.2 Finding v1
# --------------------------------------------------------------------------- #


class ModelUsage(BaseModel):
    """Token usage for a model call."""

    model_config = _CFG

    id: str
    tokens_in: int = Field(0, ge=0)
    tokens_out: int = Field(0, ge=0)


class Finding(BaseModel):
    """Structured output from a specialist agent — published to ops.findings."""

    model_config = _CFG

    schema_: Literal["ops.finding.v1"] = Field("ops.finding.v1", alias="schema")
    finding_id: str = Field(default_factory=lambda: _prefixed_id("fnd_"))
    correlation_id: str = Field(...)
    produced_at: str = Field(default_factory=_now_rfc3339)
    agent_identity: str = Field(..., description="SPIFFE URI or SA email of the producing agent.")
    domain: Literal["sre", "devsecops", "platform", "finops"]
    summary: str = Field(..., min_length=1)
    cause_hypothesis: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    impact: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="URIs of supporting evidence: log://, trace://, dashboard://",
    )
    recommendations: list[Recommendation] = Field(default_factory=list)
    model: ModelUsage


# --------------------------------------------------------------------------- #
# 4.4a ActionRequest v1
# --------------------------------------------------------------------------- #


class ActionRequest(BaseModel):
    """Emitted by the Action Broker when a proposal enters the approval queue."""

    model_config = _CFG

    schema_: Literal["ops.action_request.v1"] = Field("ops.action_request.v1", alias="schema")
    action_id: str = Field(default_factory=lambda: _prefixed_id("act_"))
    recommendation: Recommendation
    requested_by: str = Field(..., description="Agent identity that proposed this action.")
    idempotency_key: str = Field(
        default_factory=_new_uuid,
        description=(
            "Unique key for this action attempt, carried for traceability. "
            "Replay de-duplication is performed by the Broker's IdempotencyStore "
            "on (correlation_id, action_class, target), not on this field."
        ),
    )
    approval_window_until: str = Field(
        ..., description="RFC3339 timestamp after which the request expires."
    )
    correlation_id: str = Field(...)
    produced_at: str = Field(default_factory=_now_rfc3339)


# --------------------------------------------------------------------------- #
# 4.4b ActionApproval v1
# --------------------------------------------------------------------------- #


class ActionApproval(BaseModel):
    """Decision record for an approval request."""

    model_config = _CFG

    schema_: Literal["ops.action_approval.v1"] = Field("ops.action_approval.v1", alias="schema")
    action_id: str = Field(...)
    approval_id: str = Field(default_factory=lambda: _prefixed_id("apv_"))
    decision: Literal["approved", "rejected", "expired"]
    approver_identity: list[str] = Field(
        default_factory=list,
        description="SA emails or SPIFFE URIs of approvers (>=2 for prod Tier-3).",
    )
    approved_at: str = Field(default_factory=_now_rfc3339)


# --------------------------------------------------------------------------- #
# 4.4c ActionExecuted v1
# --------------------------------------------------------------------------- #


class ActionExecuted(BaseModel):
    """Emitted by the Action Broker after execution (success, failure, or rollback)."""

    model_config = _CFG

    schema_: Literal["ops.action_executed.v1"] = Field("ops.action_executed.v1", alias="schema")
    action_id: str = Field(...)
    status: Literal["success", "failed", "rolled_back"]
    outcome: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    rollback: dict[str, Any] | None = None
    produced_at: str = Field(default_factory=_now_rfc3339)


# --------------------------------------------------------------------------- #
# 4.5 OpsNotification v1
# --------------------------------------------------------------------------- #


class AffectedComponent(BaseModel):
    """Resource affected by the operational event."""

    model_config = _CFG

    type: str
    name: str
    project: str
    region: str = "europe-west2"


class NotificationRecommendedAction(BaseModel):
    """Lightweight action entry for Slack Block Kit rendering."""

    model_config = _CFG

    id: str
    label: str
    action_class: str
    tier: int = Field(..., ge=0, le=4)
    estimated_duration_s: int = Field(0, ge=0)
    reversible: bool = True


class NotificationReferences(BaseModel):
    """Deep-link references shown in the Slack message footer."""

    model_config = _CFG

    logs: str | None = None
    dashboard: str | None = None
    trace: str | None = None
    runbook: str | None = None
    scc: str | None = None
    ticket: str | None = None
    workflow: str | None = None


class NotificationAgent(BaseModel):
    """Agent metadata block attached to every notification."""

    model_config = _CFG

    identity: str
    model: str
    tokens: dict[str, int] = Field(default_factory=dict)  # {"in": N, "out": M}
    trace_id: str | None = None


class OpsNotification(BaseModel):
    """Notification published to ops.notifications — consumed by Slack-notifier.

    Schema matches Appendix C of DESIGN-REVIEW.md.
    """

    model_config = _CFG

    schema_: Literal["ops.notification.v1"] = Field("ops.notification.v1", alias="schema")
    notification_id: str = Field(default_factory=lambda: _prefixed_id("ntf_"))
    correlation_id: str = Field(...)
    produced_at: str = Field(default_factory=_now_rfc3339)
    severity: Literal["info", "low", "medium", "high", "critical"]
    environment: Literal["dev", "prod"]
    domain: Literal["sre", "devsecops", "platform", "finops", "orchestrator"]

    # Brief's required fields.
    summary: str = Field(..., min_length=1)
    affected_component: AffectedComponent
    impact: str = Field(..., min_length=1)
    recommended_actions: list[NotificationRecommendedAction] = Field(default_factory=list)
    human_required: bool
    references: NotificationReferences

    # Optional fields
    likely_cause: str | None = None
    approval_window_until: str | None = None

    # Agent metadata
    agent: NotificationAgent


# --------------------------------------------------------------------------- #
# 4.6 AuditRecord v1
# --------------------------------------------------------------------------- #


class PolicyDecision(BaseModel):
    """Policy engine decision recorded in the audit trail."""

    model_config = _CFG

    tier: int = Field(..., ge=0, le=4)
    rule: str
    outcome: Literal["approved", "denied", "expired"]


class AuditRecord(BaseModel):
    """Immutable audit record — published to ops.audit, landed in BigQuery.

    Fields per DESIGN-REVIEW §5.6.
    """

    model_config = _CFG

    audit_id: str = Field(default_factory=_new_uuid)
    correlation_id: str = Field(...)
    timestamp: str = Field(default_factory=_now_rfc3339)
    phase: Literal[
        "signal",
        "finding",
        "recommendation",
        "action_requested",
        "action_approved",
        "action_executed",
        "rollback",
    ]
    agent_identity: str = Field(...)
    human_identity: str | None = None
    environment: Literal["dev", "prod"]
    domain: Literal["sre", "devsecops", "platform", "finops", "orchestrator"]
    action_class: str | None = None
    policy_decision: PolicyDecision | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    model: ModelUsage | None = None
    outcome: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def _coerce_datetime(cls, v: object) -> str:
        """Coerce datetime objects to RFC3339 strings for consistent serialisation."""
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)
