"""Tests for aop_decommission.executor — staged, idempotent, propose-only teardown."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aop_decommission.executor import DecommissionExecutor, _classify_error
from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.planner import Planner
from aop_decommission.schemas import DecommissionPlan, ExecutionResult, ResourceRecord

_KW = {"correlation_id": "inc_test", "project": "proj", "environment": "dev"}


class FakeProposer:
    """Records every proposal and returns scripted Broker responses."""

    def __init__(self, *, default_status: str = "success") -> None:
        self.calls: list[dict[str, Any]] = []
        self.status_by_id: dict[str, str] = {}
        self.approval_window_by_id: dict[str, str] = {}
        self.fail_times: dict[str, int] = {}
        self.permanent_error: dict[str, str] = {}
        self.default_status = default_status

    def __call__(
        self,
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
        rid = str(params.get("resource_id") or target.get("name"))
        self.calls.append({"resource_id": rid, "action_class": action_class, "params": params})
        if rid in self.permanent_error:
            raise RuntimeError(self.permanent_error[rid])
        if self.fail_times.get(rid, 0) > 0:
            self.fail_times[rid] -= 1
            raise RuntimeError("service temporarily unavailable (503)")
        status = self.status_by_id.get(rid, self.default_status)
        response: dict[str, Any] = {"status": status, "detail": f"{status} for {rid}"}
        if status == "pending_approval" and rid in self.approval_window_by_id:
            response["approval_window_until"] = self.approval_window_by_id[rid]
        return response

    @property
    def called_ids(self) -> list[str]:
        return [c["resource_id"] for c in self.calls]


def _plan(resources: list[ResourceRecord]) -> DecommissionPlan:
    return Planner().plan(resources, ExemptionPolicy.empty(), **_KW)


def _status(result: ExecutionResult, rid: str) -> str:
    return next(r.status for r in result.records if r.resource_id == rid)


# --------------------------------------------------------------------------- #
# Dry-run vs live
# --------------------------------------------------------------------------- #


class TestDryRun:
    def test_dry_run_does_not_call_broker(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        plan = _plan([make_resource("a", management="unmanaged")])
        result = DecommissionExecutor(proposer, requested_by="sa-decommission").execute(
            plan, dry_run=True
        )
        assert proposer.calls == []
        assert _status(result, "a") == "proposed"
        assert result.dry_run is True

    def test_live_run_proposes_each_delete(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        plan = _plan(
            [make_resource("a", management="unmanaged"), make_resource("b", management="terraform")]
        )
        result = DecommissionExecutor(proposer, requested_by="sa").execute(plan, dry_run=False)
        assert set(proposer.called_ids) == {"a", "b"}
        assert result.executed == 2


# --------------------------------------------------------------------------- #
# Ordering + blast radius
# --------------------------------------------------------------------------- #


class TestOrdering:
    def test_proposes_in_dependency_order(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        plan = _plan(
            [
                make_resource("A", management="unmanaged", dependencies=["B"]),
                make_resource("B", management="unmanaged"),
            ]
        )
        DecommissionExecutor(proposer, requested_by="sa").execute(plan, dry_run=False)
        assert proposer.called_ids == ["A", "B"]

    def test_target_count_is_total_delete_set(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        plan = _plan(
            [make_resource("a", management="unmanaged"), make_resource("b", management="unmanaged")]
        )
        DecommissionExecutor(proposer, requested_by="sa").execute(plan, dry_run=False)
        assert all(c["params"]["target_count"] == 2 for c in proposer.calls)


# --------------------------------------------------------------------------- #
# Broker status mapping
# --------------------------------------------------------------------------- #


class TestStatusMapping:
    def test_maps_all_broker_statuses(self, make_resource: Callable[..., ResourceRecord]) -> None:
        proposer = FakeProposer()
        proposer.status_by_id = {
            "a": "already_executed",
            "b": "denied",
            "c": "pending_approval",
            "d": "success",
        }
        plan = _plan([make_resource(x, management="unmanaged") for x in ("a", "b", "c", "d")])
        result = DecommissionExecutor(
            proposer, requested_by="sa", halt_on_incomplete_stage=False
        ).execute(plan, dry_run=False)
        assert _status(result, "a") == "already_done"
        assert _status(result, "b") == "denied"
        assert _status(result, "c") == "pending_approval"
        assert _status(result, "d") == "executed"

    def test_stub_not_executed_counts_as_executed(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer(default_status="stub_not_executed")
        plan = _plan([make_resource("a", management="unmanaged")])
        result = DecommissionExecutor(proposer, requested_by="sa").execute(plan, dry_run=False)
        assert _status(result, "a") == "executed"


# --------------------------------------------------------------------------- #
# Failure handling + retries
# --------------------------------------------------------------------------- #


class TestFailureHandling:
    def test_transient_error_retries_then_succeeds(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        proposer.fail_times = {"a": 2}
        plan = _plan([make_resource("a", management="unmanaged")])
        result = DecommissionExecutor(proposer, requested_by="sa", max_attempts=3).execute(
            plan, dry_run=False
        )
        record = result.records[0]
        assert record.status == "executed"
        assert record.attempts == 3

    def test_permission_error_fails_without_retry(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        proposer.permanent_error = {"a": "permission denied (403)"}
        plan = _plan([make_resource("a", management="unmanaged")])
        result = DecommissionExecutor(proposer, requested_by="sa", max_attempts=3).execute(
            plan, dry_run=False
        )
        record = result.records[0]
        assert record.status == "failed"
        assert record.error is not None
        assert record.error.startswith("permission")
        assert record.attempts == 1

    def test_halt_on_incomplete_stage_skips_later_stages(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        proposer = FakeProposer()
        proposer.status_by_id = {"A": "denied"}
        plan = _plan(
            [
                make_resource("A", management="unmanaged", dependencies=["B"]),
                make_resource("B", management="unmanaged"),
            ]
        )
        result = DecommissionExecutor(proposer, requested_by="sa").execute(plan, dry_run=False)
        assert result.halted is True
        assert result.halt_reason is not None
        assert proposer.called_ids == ["A"]  # B never attempted
        assert _status(result, "B") == "skipped"

    @pytest.mark.parametrize(
        ("message", "category"),
        [
            ("permission denied", "permission"),
            ("resource is locked by a lien", "locked"),
            ("still has child resources", "dependency_conflict"),
            ("deadline exceeded", "transient"),
            ("something odd", "error"),
        ],
    )
    def test_error_classification(self, message: str, category: str) -> None:
        assert _classify_error(message) == category


# --------------------------------------------------------------------------- #
# Idempotency / resume
# --------------------------------------------------------------------------- #


class TestIdempotency:
    def test_resume_skips_finished_resources(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan(
            [make_resource("a", management="unmanaged"), make_resource("b", management="unmanaged")]
        )
        first = FakeProposer()
        executor = DecommissionExecutor(first, requested_by="sa")
        run1 = executor.execute(plan, dry_run=False)
        assert run1.executed == 2

        second = FakeProposer()
        run2 = DecommissionExecutor(second, requested_by="sa").execute(
            plan, dry_run=False, prior=run1
        )
        assert second.calls == []  # nothing re-proposed
        assert all(r.status == "skipped" for r in run2.records)


# --------------------------------------------------------------------------- #
# Approval-window-aware resume — re-running mid-approval must not re-queue
# the same destroy in Slack; an expired window must be re-proposed.
# --------------------------------------------------------------------------- #


class TestApprovalWindowResume:
    _NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)

    def _pending_run(
        self, plan: DecommissionPlan, window_until: str, *, now: datetime
    ) -> ExecutionResult:
        proposer = FakeProposer()
        proposer.status_by_id = {"a": "pending_approval"}
        proposer.approval_window_by_id = {"a": window_until}
        return DecommissionExecutor(proposer, requested_by="sa", now_fn=lambda: now).execute(
            plan, dry_run=False
        )

    def test_first_run_captures_approval_window(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        window = (self._NOW + timedelta(minutes=15)).isoformat()
        run1 = self._pending_run(plan, window, now=self._NOW)
        assert run1.pending_approval == 1
        assert run1.records[0].approval_window_until == window

    def test_pending_within_window_is_not_reproposed(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        window = (self._NOW + timedelta(minutes=15)).isoformat()
        run1 = self._pending_run(plan, window, now=self._NOW)

        second = FakeProposer()
        rerun_at = self._NOW + timedelta(minutes=5)  # still inside the window
        run2 = DecommissionExecutor(second, requested_by="sa", now_fn=lambda: rerun_at).execute(
            plan, dry_run=False, prior=run1
        )
        assert second.calls == []  # approval not re-queued
        assert _status(run2, "a") == "pending_approval"
        assert run2.halted is True  # stage cannot complete until the human decides

    def test_pending_after_window_expiry_is_reproposed(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        plan = _plan([make_resource("a", management="unmanaged")])
        window = (self._NOW + timedelta(minutes=15)).isoformat()
        run1 = self._pending_run(plan, window, now=self._NOW)

        second = FakeProposer()  # default success this time
        rerun_at = self._NOW + timedelta(minutes=30)  # window lapsed unanswered
        run2 = DecommissionExecutor(second, requested_by="sa", now_fn=lambda: rerun_at).execute(
            plan, dry_run=False, prior=run1
        )
        assert second.called_ids == ["a"]  # proposed afresh
        assert _status(run2, "a") == "executed"

    def test_pending_without_window_is_reproposed(
        self, make_resource: Callable[..., ResourceRecord]
    ) -> None:
        # Prior data lacking a captured window cannot prove the approval is
        # still open — the safe default is to re-propose.
        plan = _plan([make_resource("a", management="unmanaged")])
        first = FakeProposer()
        first.status_by_id = {"a": "pending_approval"}  # no window configured
        run1 = DecommissionExecutor(first, requested_by="sa").execute(plan, dry_run=False)
        assert run1.records[0].approval_window_until is None

        second = FakeProposer()
        DecommissionExecutor(second, requested_by="sa").execute(plan, dry_run=False, prior=run1)
        assert second.called_ids == ["a"]
