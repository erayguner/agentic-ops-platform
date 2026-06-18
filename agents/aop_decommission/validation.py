"""aop_decommission.validation — post-decommission re-scan and assurance.

Closure readiness is not "the executor returned success" — it is proven by
re-scanning the estate and reconciling it against the plan and the exemption
policy. This module answers four questions, each of which must hold before a
project is declared safe to close:

1. **Did every planned delete actually go?** A planned-delete resource still
   present is a ``not_deleted`` residual.
2. **Is anything billable / orphaned / unmanaged still lingering?** Non-exempt
   leftovers are residual findings — the "no dormant, orphaned, unused, billable,
   or unmanaged resources remain" guarantee.
3. **Do the survivors exactly match the approved exemptions?** Anything present
   but not exempt is ``unexpected_retained``; anything exempt but *gone* is a
   preservation gap (an exempt resource was wrongly deleted).
4. **Were the must-keep artefacts preserved?** Audit logs, billing exports,
   compliance records and backups flagged for retention must still exist.
"""

from __future__ import annotations

import logging

from aop_decommission.schemas import (
    DecommissionPlan,
    Inventory,
    ResidualFinding,
    ResourceRecord,
    RiskLevel,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Keywords that mark an exemption (by reason) or resource (by type) as a
# must-preserve artefact — used to derive the preservation set when the caller
# does not pass one explicitly.
_PRESERVATION_KEYWORDS: tuple[str, ...] = (
    "audit",
    "compliance",
    "billing",
    "backup",
    "legal",
    "retention",
    "logsink",
    "log_sink",
    "log bucket",
    "evidence",
)


class Validator:
    """Reconciles a post-decommission inventory against the plan + exemptions."""

    def validate(
        self,
        *,
        plan: DecommissionPlan,
        post_inventory: Inventory,
        preservation_required: set[str] | None = None,
    ) -> ValidationResult:
        post = post_inventory.by_id()
        result = ValidationResult(
            correlation_id=plan.correlation_id,
            project=plan.project,
        )

        expected_retained = {
            item.resource.resource_id
            for item in plan.items
            if item.disposition in ("retain_exempt", "manual_review", "skip")
        }
        planned_delete = {item.resource.resource_id for item in plan.delete_items()}

        # 1. Planned deletes that are still present.
        for item in plan.delete_items():
            if item.resource.resource_id in post:
                result.residual.append(
                    ResidualFinding(
                        resource_id=item.resource.resource_id,
                        type=item.resource.type,
                        reason="not_deleted",
                        severity=_max(item.risk, "high"),
                        detail="planned for deletion but still present in the estate",
                    )
                )

        # 2 + 3. Walk the survivors.
        for resource in post_inventory.resources:
            rid = resource.resource_id
            if rid in planned_delete:
                continue  # already captured as a not_deleted residual above
            if rid in expected_retained:
                continue  # legitimately retained
            result.unexpected_retained.append(rid)
            finding = _classify_residual(resource)
            if finding is not None:
                result.residual.append(finding)

        # 3b. Exempt resources that were wrongly removed.
        preserve = preservation_required or _derive_preservation_set(plan)
        for item in plan.items:
            if item.disposition != "retain_exempt":
                continue
            if item.resource.resource_id not in post:
                result.preservation_gaps.append(item.resource.resource_id)

        # 4. Must-preserve artefacts must still exist.
        for rid in sorted(preserve):
            if rid not in post and rid not in result.preservation_gaps:
                result.preservation_gaps.append(rid)

        result.retained_ok = not result.unexpected_retained
        result.preserved_ok = not result.preservation_gaps
        high_residual = any(r.severity in ("high", "critical") for r in result.residual)
        result.closure_ready = (
            result.retained_ok and result.preserved_ok and not result.residual and not high_residual
        )
        result.summary = _summarise(result)

        logger.info(
            "validation.validate: project=%s residual=%d unexpected=%d gaps=%d closure_ready=%s",
            plan.project,
            len(result.residual),
            len(result.unexpected_retained),
            len(result.preservation_gaps),
            result.closure_ready,
        )
        return result


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #

_RISK_ORDER: dict[RiskLevel, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _RISK_ORDER[a] >= _RISK_ORDER[b] else b


def _classify_residual(resource: ResourceRecord) -> ResidualFinding | None:
    """Flag a non-exempt survivor as a billable / unmanaged / orphaned leftover."""
    if resource.billable:
        return ResidualFinding(
            resource_id=resource.resource_id,
            type=resource.type,
            reason="residual_billable",
            severity="high",
            detail=f"still billable (~{resource.monthly_cost:.2f}/mo) and not exempt",
        )
    if resource.management in ("unmanaged", "drifted"):
        return ResidualFinding(
            resource_id=resource.resource_id,
            type=resource.type,
            reason="residual_unmanaged",
            severity="medium",
            detail=f"{resource.management} resource still present and not exempt",
        )
    if resource.has_condition("orphaned") or resource.has_condition("unattached"):
        return ResidualFinding(
            resource_id=resource.resource_id,
            type=resource.type,
            reason="residual_orphaned",
            severity="medium",
            detail="orphaned/unattached resource still present",
        )
    return None


def _derive_preservation_set(plan: DecommissionPlan) -> set[str]:
    preserve: set[str] = set()
    for item in plan.items:
        if item.disposition != "retain_exempt":
            continue
        haystack = f"{item.reason} {item.resource.type}".lower()
        if any(keyword in haystack for keyword in _PRESERVATION_KEYWORDS):
            preserve.add(item.resource.resource_id)
    return preserve


def _summarise(result: ValidationResult) -> str:
    if result.closure_ready:
        return "All non-exempt resources removed; retained set matches exemptions; artefacts preserved."
    parts: list[str] = []
    if result.residual:
        parts.append(f"{len(result.residual)} residual finding(s)")
    if result.unexpected_retained:
        parts.append(f"{len(result.unexpected_retained)} unexpected survivor(s)")
    if result.preservation_gaps:
        parts.append(f"{len(result.preservation_gaps)} preservation gap(s)")
    return "Not closure-ready: " + ", ".join(parts) + "."
