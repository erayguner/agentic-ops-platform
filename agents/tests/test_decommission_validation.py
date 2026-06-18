"""Tests for aop_decommission.validation — post-decommission assurance."""

from __future__ import annotations

from collections.abc import Callable

from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.planner import Planner
from aop_decommission.schemas import (
    DecommissionPlan,
    Inventory,
    ResourceRecord,
    ValidationResult,
)
from aop_decommission.validation import Validator

_KW = {"correlation_id": "inc_test", "project": "proj", "environment": "dev"}


def _plan(
    resources: list[ResourceRecord], policy: ExemptionPolicy | None = None
) -> DecommissionPlan:
    return Planner().plan(resources, policy or ExemptionPolicy.empty(), **_KW)


def _inv(resources: list[ResourceRecord]) -> Inventory:
    return Inventory(project="proj", environment="dev", resources=resources)


def _reasons(result: ValidationResult) -> set[str]:
    return {r.reason for r in result.residual}


# --------------------------------------------------------------------------- #
# Clean closure
# --------------------------------------------------------------------------- #


class TestCleanClosure:
    def test_all_deleted_is_closure_ready(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        result = Validator().validate(plan=plan, post_inventory=_inv([]))
        assert result.residual == []
        assert result.retained_ok is True
        assert result.preserved_ok is True
        assert result.closure_ready is True

    def test_exempt_resource_present_is_not_flagged(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "r", "name": "R"}])
        pre = [
            make_resource("R", management="terraform", name="R"),
            make_resource("a", management="unmanaged"),
        ]
        plan = _plan(pre, policy)
        result = Validator().validate(
            plan=plan, post_inventory=_inv([make_resource("R", name="R")])
        )
        assert result.unexpected_retained == []
        assert result.retained_ok is True
        assert result.closure_ready is True


# --------------------------------------------------------------------------- #
# Residuals
# --------------------------------------------------------------------------- #


class TestResiduals:
    def test_planned_delete_still_present_is_not_deleted(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        result = Validator().validate(
            plan=plan, post_inventory=_inv([make_resource("a", management="unmanaged")])
        )
        assert "not_deleted" in _reasons(result)
        assert result.closure_ready is False

    def test_residual_billable(self, make_resource: Callable[..., ResourceRecord]) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        leftover = make_resource("b", management="terraform", monthly_cost=20.0, billable=True)
        result = Validator().validate(plan=plan, post_inventory=_inv([leftover]))
        assert "residual_billable" in _reasons(result)
        assert "b" in result.unexpected_retained

    def test_residual_unmanaged(self, make_resource: Callable[..., ResourceRecord]) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        leftover = make_resource("b", management="unmanaged")
        result = Validator().validate(plan=plan, post_inventory=_inv([leftover]))
        assert "residual_unmanaged" in _reasons(result)

    def test_residual_orphaned(self, make_resource: Callable[..., ResourceRecord]) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        leftover = make_resource("b", management="terraform", conditions=["orphaned"])
        result = Validator().validate(plan=plan, post_inventory=_inv([leftover]))
        assert "residual_orphaned" in _reasons(result)

    def test_unexpected_survivor_without_residual_class(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        # terraform-managed, not billable, active → not a residual class, but still unexpected.
        leftover = make_resource("b", management="terraform")
        result = Validator().validate(plan=plan, post_inventory=_inv([leftover]))
        assert "b" in result.unexpected_retained
        assert result.retained_ok is False
        assert result.closure_ready is False


# --------------------------------------------------------------------------- #
# Preservation
# --------------------------------------------------------------------------- #


class TestPreservation:
    def test_exempt_resource_wrongly_deleted_is_a_gap(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        policy = ExemptionPolicy.from_rules([{"id": "keep", "reason": "audit", "name": "R"}])
        pre = [
            make_resource("R", management="terraform", name="R"),
            make_resource("a", management="unmanaged"),
        ]
        plan = _plan(pre, policy)
        # R is gone from the post inventory — it should have been retained.
        result = Validator().validate(plan=plan, post_inventory=_inv([]))
        assert "R" in result.preservation_gaps
        assert result.preserved_ok is False
        assert result.closure_ready is False

    def test_explicit_preservation_required_missing_is_a_gap(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        result = Validator().validate(
            plan=plan,
            post_inventory=_inv([]),
            preservation_required={"audit-sink-1"},
        )
        assert "audit-sink-1" in result.preservation_gaps
        assert result.preserved_ok is False
