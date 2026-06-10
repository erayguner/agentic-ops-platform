"""Tests for aop_decommission.planner — disposition, ordering, retention cascade."""

from __future__ import annotations

from collections.abc import Callable

from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.planner import Planner
from aop_decommission.schemas import DecommissionPlan, PlanItem, ResourceRecord

_KW = {"correlation_id": "inc_test", "project": "proj", "environment": "dev"}


def _plan(
    resources: list[ResourceRecord], policy: ExemptionPolicy | None = None
) -> DecommissionPlan:
    return Planner().plan(resources, policy or ExemptionPolicy.empty(), **_KW)


def _item(plan: DecommissionPlan, resource_id: str) -> PlanItem:
    return next(i for i in plan.items if i.resource.resource_id == resource_id)


# --------------------------------------------------------------------------- #
# Disposition by management state
# --------------------------------------------------------------------------- #


class TestDisposition:
    def test_terraform_resource_is_destroy_target(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="terraform", terraform_address="module.a.x")])
        item = _item(plan, "a")
        assert item.disposition == "delete"
        assert item.method == "terraform_destroy"
        assert item.action_class == "terraform.destroy_target"
        assert item.reversible is False
        assert item.proposed_tier == 3

    def test_unmanaged_resource_is_provider_delete(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        item = _item(plan, "a")
        assert item.disposition == "delete"
        assert item.action_class == "decommission.delete_resource"

    def test_drifted_resource_is_provider_delete(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        item = _item(_plan([make_resource("a", management="drifted")]), "a")
        assert item.disposition == "delete"
        assert item.action_class == "decommission.delete_resource"

    def test_ghost_resource_is_skipped(self, make_resource: Callable[..., ResourceRecord]) -> None:
        item = _item(_plan([make_resource("a", management="ghost")]), "a")
        assert item.disposition == "skip"

    def test_unknown_management_is_manual_review(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        item = _item(_plan([make_resource("a", management="unknown")]), "a")
        assert item.disposition == "manual_review"

    def test_iac_other_is_manual_review(self, make_resource: Callable[..., ResourceRecord]) -> None:
        item = _item(_plan([make_resource("a", management="iac_other")]), "a")
        assert item.disposition == "manual_review"

    def test_exempt_resource_is_retained(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules(
            [{"id": "keep", "reason": "audit", "service": "logging"}]
        )
        plan = _plan([make_resource("a", management="terraform", service="logging")], policy)
        item = _item(plan, "a")
        assert item.disposition == "retain_exempt"
        assert item.exemption is not None
        assert item.exemption.rule_id == "keep"


# --------------------------------------------------------------------------- #
# Dependency-ordered deletion
# --------------------------------------------------------------------------- #


class TestOrdering:
    def test_dependent_deleted_before_dependency(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        # A depends on B → A must be torn down first (earlier stage).
        resources = [
            make_resource("A", management="unmanaged", dependencies=["B"]),
            make_resource("B", management="unmanaged"),
        ]
        plan = _plan(resources)
        assert _item(plan, "A").stage == 0
        assert _item(plan, "B").stage == 1
        assert len(plan.stages) == 2

    def test_independent_resources_share_stage_zero(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan(
            [make_resource("A", management="unmanaged"), make_resource("B", management="unmanaged")]
        )
        assert _item(plan, "A").stage == 0
        assert _item(plan, "B").stage == 0

    def test_dependency_cycle_routed_to_manual_review(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        resources = [
            make_resource("A", management="unmanaged", dependencies=["B"]),
            make_resource("B", management="unmanaged", dependencies=["A"]),
        ]
        plan = _plan(resources)
        assert _item(plan, "A").disposition == "manual_review"
        assert _item(plan, "B").disposition == "manual_review"
        assert any("cycle" in r for r in plan.risks)


# --------------------------------------------------------------------------- #
# Transitive retention — nothing a retained resource needs gets deleted
# --------------------------------------------------------------------------- #


class TestTransitiveRetention:
    def test_dependency_of_retained_is_demoted(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "exempt", "name": "R"}])
        resources = [
            make_resource("R", management="terraform", name="R", dependencies=["D"]),
            make_resource("D", management="unmanaged", name="D"),
        ]
        plan = _plan(resources, policy)
        assert _item(plan, "R").disposition == "retain_exempt"
        assert _item(plan, "D").disposition == "manual_review"
        assert "required by retained" in _item(plan, "D").reason

    def test_retention_cascades_through_chain(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "exempt", "name": "R"}])
        resources = [
            make_resource("R", management="terraform", name="R", dependencies=["D"]),
            make_resource("D", management="unmanaged", name="D", dependencies=["E"]),
            make_resource("E", management="unmanaged", name="E"),
        ]
        plan = _plan(resources, policy)
        assert _item(plan, "D").disposition == "manual_review"
        assert _item(plan, "E").disposition == "manual_review"


# --------------------------------------------------------------------------- #
# Risk + aggregates
# --------------------------------------------------------------------------- #


class TestRiskAndAggregates:
    def test_security_sensitive_delete_is_high_risk(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        item = _item(
            _plan([make_resource("a", management="unmanaged", security_sensitive=True)]), "a"
        )
        assert item.risk == "high"

    def test_critical_sensitive_is_critical_risk(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        item = _item(
            _plan(
                [
                    make_resource(
                        "a",
                        management="unmanaged",
                        security_sensitive=True,
                        criticality="critical",
                    )
                ]
            ),
            "a",
        )
        assert item.risk == "critical"

    def test_counts_and_savings(self, make_resource: Callable[..., ResourceRecord]) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "r", "name": "keepme"}])
        resources = [
            make_resource("a", management="terraform", service="run", monthly_cost=10.0),
            make_resource("b", management="unmanaged", service="compute", monthly_cost=5.5),
            make_resource("keepme", management="terraform", name="keepme"),
            make_resource("ghost", management="ghost"),
        ]
        plan = _plan(resources, policy)
        assert plan.to_delete == 2
        assert plan.retained_exempt == 1
        assert plan.skipped == 1
        assert plan.irreversible == 2
        assert plan.estimated_monthly_savings == 15.5
        assert plan.by_service == {"run": 1, "compute": 1}

    def test_irreversible_risk_is_flagged(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="terraform")])
        assert any("irreversible" in r for r in plan.risks)

    def test_billable_exempt_resource_flagged_as_ongoing_cost(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "r", "name": "keepme"}])
        plan = _plan(
            [
                make_resource(
                    "keepme",
                    management="terraform",
                    name="keepme",
                    monthly_cost=99.0,
                    billable=True,
                )
            ],
            policy,
        )
        assert any("billable" in r for r in plan.risks)
