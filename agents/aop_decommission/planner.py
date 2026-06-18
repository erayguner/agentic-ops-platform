"""aop_decommission.planner — the dry-run plan and safe deletion ordering.

Turns an :class:`Inventory` plus an :class:`ExemptionPolicy` into a
:class:`DecommissionPlan` that states, per resource, exactly what will be
deleted, retained, skipped, or flagged for manual review — *before* anything
destructive happens.

Two correctness properties carry the safety of the whole campaign:

1. **Retention is transitive.** If a retained resource (exempt or manual-review)
   depends on a delete-candidate, that candidate is demoted to manual review and
   the demotion cascades, so teardown can never sever a dependency of something
   that must survive.
2. **Deletion is dependency-ordered.** Delete-candidates are partitioned into
   stages by a topological sort over their dependencies: a resource is only
   scheduled once everything that depends on it is already scheduled earlier.
   Dependency cycles are not guessed at — they are routed to manual review.
"""

from __future__ import annotations

import logging

from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.schemas import (
    DecommissionPlan,
    DeletionMethod,
    DeletionStage,
    ManagementState,
    PlanItem,
    ResourceRecord,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Agents always *propose* destroys at Tier 3 (human-approved). The Broker policy
# sets the final tier and approver count per environment; an agent never asks for
# Tier 4 (autonomous) on an irreversible delete.
_PROPOSED_DESTROY_TIER = 3

# management state → (deletion method, broker action class, reversible)
_DELETION_SPEC: dict[ManagementState, tuple[DeletionMethod, str | None, bool]] = {
    "terraform": ("terraform_destroy", "terraform.destroy_target", False),
    "drifted": ("provider_delete", "decommission.delete_resource", False),
    "unmanaged": ("provider_delete", "decommission.delete_resource", False),
}


class Planner:
    """Builds a DecommissionPlan from an inventory + exemption policy."""

    def __init__(
        self,
        *,
        dormant_required_for_unmanaged: bool = False,
    ) -> None:
        # When True, an unmanaged resource is only auto-targeted for deletion if
        # it is also dormant/stale; otherwise it is routed to manual review. The
        # conservative default (False) targets all non-exempt unmanaged resources
        # but every destroy still passes the Broker approval gate.
        self._dormant_required_for_unmanaged = dormant_required_for_unmanaged

    def plan(
        self,
        inventory_resources: list[ResourceRecord],
        policy: ExemptionPolicy,
        *,
        correlation_id: str,
        project: str,
        environment: str,
    ) -> DecommissionPlan:
        items: dict[str, PlanItem] = {}

        # 1. First pass — exemption, then management-driven disposition.
        for resource in inventory_resources:
            match = policy.evaluate(resource)
            if match is not None:
                items[resource.resource_id] = PlanItem(
                    resource=resource,
                    disposition="retain_exempt",
                    reason=f"exempt by rule {match.rule_id}: {match.reason}",
                    reversible=True,
                    exemption=match,
                    risk="low",
                )
                continue
            items[resource.resource_id] = self._disposition_for(resource)

        # 2. Transitive retention — nothing a retained resource needs gets deleted.
        self._protect_dependencies_of_retained(items)

        # 3. Dependency-ordered deletion stages over the surviving delete-set.
        delete_ids = {rid for rid, item in items.items() if item.disposition == "delete"}
        deps = {rid: items[rid].resource.dependencies for rid in delete_ids}
        stages, cyclic = _order_deletion(delete_ids, deps)

        for rid in cyclic:
            item = items[rid]
            item.disposition = "manual_review"
            item.reason = "in a dependency cycle — deletion order cannot be derived automatically"
            item.risk = _max_risk(item.risk, "high")
            item.method = None
            item.action_class = None
            item.stage = None

        deletion_stages: list[DeletionStage] = []
        for index, stage_ids in enumerate(stages):
            for rid in stage_ids:
                items[rid].stage = index
            deletion_stages.append(DeletionStage(index=index, resource_ids=sorted(stage_ids)))

        return self._assemble(
            list(items.values()),
            deletion_stages,
            cyclic_count=len(cyclic),
            correlation_id=correlation_id,
            project=project,
            environment=environment,
        )

    # ------------------------------------------------------------------ #
    # Disposition
    # ------------------------------------------------------------------ #

    def _disposition_for(self, resource: ResourceRecord) -> PlanItem:
        state = resource.management

        if state == "ghost":
            return PlanItem(
                resource=resource,
                disposition="skip",
                reason="absent from the live estate — already deleted out of band",
                reversible=True,
                risk="low",
            )
        if state in ("iac_other", "unknown"):
            return PlanItem(
                resource=resource,
                disposition="manual_review",
                reason=f"management state {state!r} — operator must confirm ownership before teardown",
                reversible=True,
                risk="medium",
            )

        if (
            state == "unmanaged"
            and self._dormant_required_for_unmanaged
            and not (resource.has_condition("dormant") or resource.has_condition("stale"))
        ):
            return PlanItem(
                resource=resource,
                disposition="manual_review",
                reason="unmanaged but still active — confirm it is safe to remove",
                reversible=True,
                risk="medium",
            )

        method, action_class, reversible = _DELETION_SPEC[state]
        risk = _assess_risk(resource, reversible=reversible)
        return PlanItem(
            resource=resource,
            disposition="delete",
            reason=_delete_reason(resource),
            method=method,
            action_class=action_class,
            proposed_tier=_PROPOSED_DESTROY_TIER,
            reversible=reversible,
            risk=risk,
        )

    def _protect_dependencies_of_retained(self, items: dict[str, PlanItem]) -> None:
        """Cascade: anything a retained/manual resource depends on is also retained."""
        retained = {
            rid
            for rid, item in items.items()
            if item.disposition in ("retain_exempt", "manual_review")
        }
        worklist = list(retained)
        while worklist:
            rid = worklist.pop()
            item = items.get(rid)
            if item is None:
                continue
            for dep_id in item.resource.dependencies:
                dep_item = items.get(dep_id)
                if dep_item is None or dep_item.disposition != "delete":
                    continue
                dep_item.disposition = "manual_review"
                dep_item.reason = (
                    f"required by retained resource {rid} — cannot be torn down automatically"
                )
                dep_item.risk = _max_risk(dep_item.risk, "high")
                dep_item.method = None
                dep_item.action_class = None
                dep_item.proposed_tier = None
                retained.add(dep_id)
                worklist.append(dep_id)

    # ------------------------------------------------------------------ #
    # Assembly
    # ------------------------------------------------------------------ #

    def _assemble(
        self,
        items: list[PlanItem],
        stages: list[DeletionStage],
        *,
        cyclic_count: int,
        correlation_id: str,
        project: str,
        environment: str,
    ) -> DecommissionPlan:
        delete_items = [i for i in items if i.disposition == "delete"]
        by_service: dict[str, int] = {}
        for item in delete_items:
            by_service[item.resource.service] = by_service.get(item.resource.service, 0) + 1

        irreversible = sum(1 for i in delete_items if not i.reversible)
        savings = round(sum(i.resource.monthly_cost for i in delete_items), 2)

        risks: list[str] = []
        if irreversible:
            risks.append(f"{irreversible} irreversible destroy action(s) — no rollback after apply")
        if cyclic_count:
            risks.append(f"{cyclic_count} resource(s) in dependency cycles routed to manual review")
        sensitive = sum(1 for i in delete_items if i.resource.security_sensitive)
        if sensitive:
            risks.append(
                f"{sensitive} security-sensitive resource(s) targeted — verify before approval"
            )
        billable_retained = sum(
            1 for i in items if i.disposition == "retain_exempt" and i.resource.billable
        )
        if billable_retained:
            risks.append(
                f"{billable_retained} exempt resource(s) remain billable — ongoing cost by design"
            )

        plan = DecommissionPlan(
            correlation_id=correlation_id,
            project=project,
            environment=environment,
            items=sorted(
                items,
                key=lambda i: (i.stage if i.stage is not None else 1_000, i.resource.resource_id),
            ),
            stages=stages,
            to_delete=len(delete_items),
            retained_exempt=sum(1 for i in items if i.disposition == "retain_exempt"),
            skipped=sum(1 for i in items if i.disposition == "skip"),
            manual_review=sum(1 for i in items if i.disposition == "manual_review"),
            irreversible=irreversible,
            estimated_monthly_savings=savings,
            by_service=by_service,
            risks=risks,
        )
        logger.info(
            "planner.plan: project=%s delete=%d retain=%d skip=%d manual=%d stages=%d",
            project,
            plan.to_delete,
            plan.retained_exempt,
            plan.skipped,
            plan.manual_review,
            len(stages),
        )
        return plan


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #

_RISK_ORDER: dict[RiskLevel, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _RISK_ORDER[a] >= _RISK_ORDER[b] else b


def _assess_risk(resource: ResourceRecord, *, reversible: bool) -> RiskLevel:
    risk: RiskLevel = "low"
    if not reversible:
        risk = _max_risk(risk, "medium")
    if resource.criticality in ("high", "critical"):
        risk = _max_risk(risk, "high")
    if resource.security_sensitive:
        risk = _max_risk(risk, "high")
    if resource.criticality == "critical" and resource.security_sensitive:
        risk = "critical"
    return risk


def _delete_reason(resource: ResourceRecord) -> str:
    bits: list[str] = [f"{resource.management} resource"]
    if resource.conditions:
        bits.append("; ".join(resource.conditions))
    if resource.billable:
        bits.append(f"~{resource.monthly_cost:.2f}/mo")
    return ", ".join(bits)


def _order_deletion(
    delete_ids: set[str], deps: dict[str, list[str]]
) -> tuple[list[list[str]], set[str]]:
    """Topologically stage deletions; return (stages, cyclic_remainder).

    ``deps[r]`` lists what ``r`` depends ON. A resource is only ready to delete
    once everything that depends on it is already staged, so stage 0 holds the
    resources nothing (in the delete-set) depends on. Anything never reachable is
    in a cycle and returned separately for manual handling.
    """
    dependents: dict[str, set[str]] = {rid: set() for rid in delete_ids}
    for rid in delete_ids:
        for dep in deps.get(rid, []):
            if dep in delete_ids:
                dependents[dep].add(rid)

    remaining = {rid: set(value) for rid, value in dependents.items()}
    placed: set[str] = set()
    stages: list[list[str]] = []

    while True:
        ready = sorted(rid for rid in delete_ids if rid not in placed and not remaining[rid])
        if not ready:
            break
        stages.append(ready)
        for rid in ready:
            placed.add(rid)
            for dep in deps.get(rid, []):
                if dep in remaining:
                    remaining[dep].discard(rid)

    cyclic = delete_ids - placed
    return stages, cyclic
