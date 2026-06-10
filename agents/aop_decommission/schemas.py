"""aop_decommission.schemas — decommission-campaign domain models (Pydantic v2).

The agent-local vocabulary for the full project-closure lifecycle:

    discover → inventory → exempt → plan → execute → validate → report

Cross-boundary messages (``Finding``, ``Recommendation``, ``OpsNotification``,
``AuditRecord``) reuse ``aop_common.schemas`` — these models are the *internal*
contract the engine modules (``inventory``, ``exemptions``, ``planner``,
``executor``, ``validation``, ``report``) hand to one another. Keeping them here,
not in ``aop_common``, mirrors how each ``services/*`` component owns its own
``schemas.py``: only what crosses the Pub/Sub spine lives in the shared module.

Conventions match ``aop_common.schemas``: snake_case, ``strict=True``, RFC3339
timestamps, prefixed ids supplied by default factories.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_CFG = ConfigDict(strict=True, populate_by_name=True)


def _now_rfc3339() -> str:
    return datetime.now(UTC).isoformat()


def _prefixed_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

# How a resource is (or is not) managed by infrastructure-as-code.
ManagementState = Literal[
    "terraform",  # tracked in Terraform state
    "iac_other",  # managed by another IaC tool (Config Connector, Deployment Manager)
    "unmanaged",  # exists in the estate but no IaC declares it (manually created)
    "drifted",  # claims management (e.g. managed_by=terraform label) but absent from state
    "ghost",  # in IaC state but absent from the live estate (already gone / out-of-band delete)
    "unknown",
]

# Non-exclusive lifecycle conditions. A single resource may be several at once
# (e.g. dormant *and* unattached *and* billable).
ResourceCondition = Literal[
    "dormant",  # no activity within the dormancy window
    "stale",  # no activity within the (longer) staleness window
    "unused",  # provisioned capacity with zero utilisation
    "orphaned",  # owning/parent resource is gone
    "unattached",  # attachable resource (disk, IP, NIC) bound to nothing
]

Criticality = Literal["critical", "high", "medium", "low", "unknown"]

DiscoverySource = Literal["terraform_state", "asset_inventory", "recommender", "manual"]

# What the planner decides to do with each inventoried resource.
Disposition = Literal["delete", "retain_exempt", "skip", "manual_review"]

# How a delete-disposition resource would be torn down.
DeletionMethod = Literal["terraform_destroy", "provider_delete", "manual"]

RiskLevel = Literal["low", "medium", "high", "critical"]

# Per-resource outcome of an execution attempt (proposals to the Action Broker).
ExecutionStatus = Literal[
    "proposed",  # dry-run: would be proposed, Broker not called
    "pending_approval",  # Broker queued it for human (Tier 3/4) approval
    "executed",  # Broker accepted + executed (or stub-executed under LIVE_MODE=false)
    "denied",  # Broker policy denied it
    "failed",  # executor error after retries
    "skipped",  # not attempted (e.g. prior stage halted, or not a delete item)
    "already_done",  # idempotency hit — Broker had executed it before
]

# Why a residual resource is flagged by post-decommission validation.
ResidualReason = Literal[
    "not_deleted",  # a planned-delete resource is still present
    "residual_billable",  # still incurring cost and not exempt
    "residual_orphaned",  # orphaned/unattached leftover
    "residual_unmanaged",  # unmanaged resource still present and not exempt
]


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #


class ResourceRecord(BaseModel):
    """A single discovered resource with ownership, cost, risk and dependency facts.

    ``resource_id`` is the canonical full identifier (Cloud Asset Inventory
    ``//service.googleapis.com/projects/<p>/.../name``) and is the merge key
    across discovery sources.
    """

    model_config = _CFG

    resource_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1, description="Asset type, e.g. run.googleapis.com/Service.")
    service: str = Field(
        ..., min_length=1, description="Short service code, e.g. run, compute, iam."
    )
    project: str = Field(..., min_length=1)
    location: str = "global"

    management: ManagementState = "unknown"
    terraform_address: str | None = Field(
        None, description="Address in Terraform state (module.x.google_*), when managed."
    )

    owner: str | None = None
    environment: str | None = None
    criticality: Criticality = "unknown"
    labels: dict[str, str] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict, description="Resource Manager tag bindings.")

    created_at: str | None = None
    last_activity_at: str | None = Field(
        None, description="RFC3339 of last observed activity; None when unknown."
    )

    monthly_cost: float = Field(
        0.0, ge=0.0, description="Estimated cost/month in billing currency."
    )
    billable: bool = False
    security_sensitive: bool = Field(
        False, description="Keys, SAs, secrets, KMS, audit sinks — handle with extra care."
    )

    conditions: list[ResourceCondition] = Field(default_factory=list)
    dependencies: list[str] = Field(
        default_factory=list, description="resource_ids this resource depends ON (needs)."
    )
    discovered_by: list[DiscoverySource] = Field(default_factory=list)

    def has_condition(self, condition: ResourceCondition) -> bool:
        return condition in self.conditions


class Inventory(BaseModel):
    """The complete pre-/post-decommission snapshot of the project's estate."""

    model_config = _CFG

    inventory_id: str = Field(default_factory=lambda: _prefixed_id("inv_"))
    project: str = Field(..., min_length=1)
    environment: str
    captured_at: str = Field(default_factory=_now_rfc3339)
    resources: list[ResourceRecord] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.resources)

    def by_id(self) -> dict[str, ResourceRecord]:
        return {r.resource_id: r for r in self.resources}


# --------------------------------------------------------------------------- #
# Exemptions
# --------------------------------------------------------------------------- #


class ExemptionRule(BaseModel):
    """One policy-driven retention rule. A ``reason`` is mandatory.

    Match criteria are ANDed: every populated field must match for the rule to
    apply. ``name``/``type``/``service`` support ``fnmatch`` globs. ``label_selector``
    and ``tag_selector`` require every listed key/value to be present.
    """

    model_config = _CFG

    id: str = Field(..., min_length=1)
    reason: str = Field(
        ..., min_length=1, description="Mandatory justification; appears in the report."
    )

    resource_id: str | None = None
    type: str | None = None
    name: str | None = None
    service: str | None = None
    environment: str | None = None
    owner: str | None = None
    criticality: Criticality | None = None
    label_selector: dict[str, str] = Field(default_factory=dict)
    tag_selector: dict[str, str] = Field(default_factory=dict)

    expires_at: str | None = Field(
        None, description="Optional RFC3339 expiry; an expired rule no longer protects."
    )

    def is_empty(self) -> bool:
        """True if the rule has no match criteria (would match everything — refused)."""
        return not any(
            [
                self.resource_id,
                self.type,
                self.name,
                self.service,
                self.environment,
                self.owner,
                self.criticality,
                self.label_selector,
                self.tag_selector,
            ]
        )


class ExemptionMatch(BaseModel):
    """Record that a resource was retained by a specific exemption rule."""

    model_config = _CFG

    resource_id: str
    rule_id: str
    reason: str
    matched_on: list[str] = Field(default_factory=list, description="Dimensions that matched.")


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #


class PlanItem(BaseModel):
    """The decision for a single resource: delete / retain / skip / manual-review."""

    model_config = _CFG

    resource: ResourceRecord
    disposition: Disposition
    reason: str = Field(..., min_length=1)

    method: DeletionMethod | None = None
    action_class: str | None = None
    proposed_tier: int | None = Field(None, ge=0, le=4)
    risk: RiskLevel = "low"
    reversible: bool = True
    stage: int | None = Field(None, ge=0, description="Deletion stage; None for non-delete items.")
    exemption: ExemptionMatch | None = None


class DeletionStage(BaseModel):
    """A dependency-ordered batch — every item is safe to delete in parallel."""

    model_config = _CFG

    index: int = Field(..., ge=0)
    resource_ids: list[str] = Field(default_factory=list)


class DecommissionPlan(BaseModel):
    """The dry-run plan: exactly what will be deleted, retained, skipped, flagged."""

    model_config = _CFG

    plan_id: str = Field(default_factory=lambda: _prefixed_id("plan_"))
    correlation_id: str = Field(..., min_length=1)
    project: str = Field(..., min_length=1)
    environment: str
    created_at: str = Field(default_factory=_now_rfc3339)

    items: list[PlanItem] = Field(default_factory=list)
    stages: list[DeletionStage] = Field(default_factory=list)

    to_delete: int = 0
    retained_exempt: int = 0
    skipped: int = 0
    manual_review: int = 0
    irreversible: int = 0
    estimated_monthly_savings: float = 0.0
    by_service: dict[str, int] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)

    def delete_items(self) -> list[PlanItem]:
        return [i for i in self.items if i.disposition == "delete"]


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


class ExecutionRecord(BaseModel):
    """The full, audit-grade trace of one resource's teardown attempt."""

    model_config = _CFG

    resource_id: str
    action_class: str | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    status: ExecutionStatus
    broker_status: str | None = Field(None, description="Raw status returned by the Broker.")
    attempts: int = 0
    stage: int | None = None
    started_at: str = Field(default_factory=_now_rfc3339)
    finished_at: str | None = None
    detail: str | None = None
    error: str | None = None
    idempotency_key: str | None = None


class ExecutionResult(BaseModel):
    """Aggregate outcome of an execution run (dry-run or live proposals)."""

    model_config = _CFG

    run_id: str = Field(default_factory=lambda: _prefixed_id("run_"))
    correlation_id: str = Field(..., min_length=1)
    dry_run: bool = True
    started_at: str = Field(default_factory=_now_rfc3339)
    finished_at: str | None = None
    records: list[ExecutionRecord] = Field(default_factory=list)

    executed: int = 0
    pending_approval: int = 0
    denied: int = 0
    failed: int = 0
    skipped: int = 0
    halted: bool = False
    halt_reason: str | None = None


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


class ResidualFinding(BaseModel):
    """A resource that should be gone (or accounted for) but still lingers."""

    model_config = _CFG

    resource_id: str
    type: str
    reason: ResidualReason
    severity: RiskLevel
    detail: str | None = None


class ValidationResult(BaseModel):
    """Post-decommission assurance: did the campaign do what the plan promised?"""

    model_config = _CFG

    validation_id: str = Field(default_factory=lambda: _prefixed_id("val_"))
    correlation_id: str = Field(..., min_length=1)
    project: str
    validated_at: str = Field(default_factory=_now_rfc3339)

    residual: list[ResidualFinding] = Field(default_factory=list)
    unexpected_retained: list[str] = Field(
        default_factory=list, description="Present but not covered by any exemption."
    )
    preservation_gaps: list[str] = Field(
        default_factory=list, description="Required-to-preserve resources that went missing."
    )

    retained_ok: bool = True
    preserved_ok: bool = True
    closure_ready: bool = False
    summary: str = ""


# --------------------------------------------------------------------------- #
# Final report
# --------------------------------------------------------------------------- #


class DecommissionReport(BaseModel):
    """The comprehensive end report confirming project-closure readiness."""

    model_config = _CFG

    report_id: str = Field(default_factory=lambda: _prefixed_id("rpt_"))
    correlation_id: str = Field(..., min_length=1)
    project: str
    environment: str
    generated_at: str = Field(default_factory=_now_rfc3339)
    mode: Literal["plan", "execute"] = "plan"

    initial_count: int = 0
    deleted: list[str] = Field(default_factory=list)
    retained_exempt: list[ExemptionMatch] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    manual_review: list[str] = Field(default_factory=list)
    pending_approval: list[str] = Field(default_factory=list)

    remaining_risks: list[str] = Field(default_factory=list)
    estimated_monthly_savings: float = 0.0
    currency: str = "GBP"

    validation: ValidationResult | None = None
    closure_ready: bool = False
