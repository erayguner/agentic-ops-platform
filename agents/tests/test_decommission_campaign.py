"""Tests for aop_decommission.campaign — the end-to-end lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aop_decommission.campaign import DecommissionCampaign
from aop_decommission.executor import DecommissionExecutor
from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.inventory import InventoryScanner
from aop_decommission.planner import Planner
from aop_decommission.schemas import DiscoverySource, ResourceRecord
from aop_decommission.validation import Validator


class _SeqSource:
    """A provider returning successive estate snapshots (pre-, then post-teardown)."""

    source: DiscoverySource = "asset_inventory"

    def __init__(self, snapshots: list[list[ResourceRecord]]) -> None:
        self._snapshots = snapshots
        self._index = 0

    def discover(self) -> list[ResourceRecord]:
        snap = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        return [r.model_copy(deep=True) for r in snap]


def _ok_proposer(
    *,
    action_class: str,
    target: dict[str, Any],
    params: dict[str, Any],
    proposed_tier: int,
    rationale: str,
    correlation_id: str,
    environment: str,
    requested_by: str,
) -> dict[str, Any]:
    return {"status": "success", "detail": "ok"}


def _campaign(
    snapshots: list[list[ResourceRecord]],
    *,
    audit_log: list[str] | None = None,
    with_executor: bool = False,
) -> DecommissionCampaign:
    scanner = InventoryScanner([_SeqSource(snapshots)])
    executor = (
        DecommissionExecutor(_ok_proposer, requested_by="sa-decommission")
        if with_executor
        else None
    )
    sink = (lambda phase, _payload: audit_log.append(phase)) if audit_log is not None else None
    return DecommissionCampaign(
        scanner=scanner,
        policy=ExemptionPolicy.empty(),
        planner=Planner(),
        executor=executor,
        validator=Validator(),
        correlation_id="inc_test",
        project="proj",
        environment="dev",
        audit=sink,
    )


class TestPlanMode:
    def test_plan_mode_produces_plan_without_executing(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        audit: list[str] = []
        campaign = _campaign([[make_resource("a", management="unmanaged")]], audit_log=audit)
        outcome = campaign.run(mode="plan")

        assert outcome.execution is None
        assert outcome.plan.to_delete == 1
        assert outcome.validation is None
        assert "finding" in audit  # inventory phase
        assert "recommendation" in audit  # plan phase

    def test_report_markdown_renders(self, make_resource: Callable[..., ResourceRecord]) -> None:
        campaign = _campaign([[make_resource("a", management="unmanaged")]])
        outcome = campaign.run(mode="plan")
        assert "Decommission Report" in outcome.report_markdown()


class TestExecuteMode:
    def test_execute_mode_tears_down_and_validates_clean(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        audit: list[str] = []
        # Snapshot 0 = full estate; snapshot 1 = after teardown (empty).
        campaign = _campaign(
            [[make_resource("a", management="unmanaged")], []],
            audit_log=audit,
            with_executor=True,
        )
        outcome = campaign.run(mode="execute")

        assert outcome.execution is not None
        assert outcome.execution.executed == 1
        assert outcome.post_inventory is not None
        assert outcome.post_inventory.count == 0
        assert outcome.validation is not None
        assert outcome.validation.closure_ready is True
        assert outcome.report.closure_ready is True
        assert "action_executed" in audit

    def test_execute_mode_flags_residual_when_not_removed(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        # Post-scan still shows the resource → validation must catch it.
        resource = make_resource("a", management="unmanaged")
        campaign = _campaign([[resource], [resource]], with_executor=True)
        outcome = campaign.run(mode="execute")
        assert outcome.validation is not None
        assert outcome.validation.closure_ready is False
        assert any(r.reason == "not_deleted" for r in outcome.validation.residual)
