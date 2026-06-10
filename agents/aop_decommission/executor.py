"""aop_decommission.executor — staged, idempotent teardown via the Action Broker.

The executor is the campaign's hands, but it has none of its own: it **never
calls a delete API**. Every teardown is a ``propose_action`` to the Action Broker
— the single execution choke point — which independently policy-gates the action,
routes Tier-3/4 destroys to human approval, and only then runs the LIVE_MODE-gated
executor. That structural fact (there is no cloud-mutation call anywhere in this
module) is what makes the agent safe to deploy with read-only IAM.

Behaviour required of a robust teardown engine, all implemented here:

* **Dependency-ordered** — walks the planner's stages in order.
* **Idempotent + resumable** — a prior :class:`ExecutionResult` short-circuits
  finished resources, and the Broker itself de-duplicates on
  ``(correlation_id, action_class, target)``, so re-running is always safe.
* **Partial-failure aware** — classifies locked / permission / dependency /
  transient errors, retries only the transient ones, and records every attempt.
* **Stage-safe halting** — if a stage cannot fully complete (a failure, denial,
  or pending human approval), later stages are not attempted, because their
  resources may depend on the unfinished ones. Re-run after resolution resumes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from aop_decommission.schemas import (
    DecommissionPlan,
    ExecutionRecord,
    ExecutionResult,
    ExecutionStatus,
    PlanItem,
)

logger = logging.getLogger(__name__)

# Broker response status → our ExecutionStatus.
_BROKER_STATUS_MAP: dict[str, ExecutionStatus] = {
    "success": "executed",
    "stub_not_executed": "executed",  # Broker accepted; its own LIVE_MODE gates the real call
    "already_executed": "already_done",
    "denied": "denied",
    "pending_approval": "pending_approval",
    "rolled_back": "failed",
}

# Error-text markers used to classify executor exceptions.
_PERMISSION_MARKERS = ("permission", "forbidden", "denied", "unauthor", "403")
_LOCKED_MARKERS = ("locked", "lien", "in use", "resource is being used", "conflict", "409")
_DEPENDENCY_MARKERS = ("depend", "in use by", "still has", "not empty", "child resources")
_TRANSIENT_MARKERS = ("timeout", "deadline", "unavailable", "temporarily", "503", "429", "500")

# Statuses that count as "this resource is finished" for resume + stage-completion.
_DONE_STATUSES: frozenset[ExecutionStatus] = frozenset({"executed", "already_done"})


class ActionProposer(Protocol):
    """Proposes a single action to the Action Broker and returns its response dict."""

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
    ) -> dict[str, Any]: ...


class DecommissionExecutor:
    """Executes a DecommissionPlan by proposing each destroy to the Action Broker.

    Args:
        proposer: Callable that submits one action to the Broker. Inject a fake
            in tests; in production wrap ``aop_common.action_client``.
        requested_by: Agent identity recorded on every proposal for audit.
        terraform_working_dir: ``working_dir`` passed to ``terraform.destroy_target``.
        max_attempts: Attempts per resource before giving up (transient errors only).
        halt_on_incomplete_stage: Stop before the next stage when the current one
            is not fully torn down (the safe default for dependency-ordered work).
        now_fn: Injectable clock.
    """

    def __init__(
        self,
        proposer: ActionProposer,
        *,
        requested_by: str,
        terraform_working_dir: str = "",
        max_attempts: int = 3,
        halt_on_incomplete_stage: bool = True,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._proposer = proposer
        self._requested_by = requested_by
        self._tf_working_dir = terraform_working_dir
        self._max_attempts = max(1, max_attempts)
        self._halt_on_incomplete_stage = halt_on_incomplete_stage
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    def execute(
        self,
        plan: DecommissionPlan,
        *,
        dry_run: bool = True,
        prior: ExecutionResult | None = None,
    ) -> ExecutionResult:
        """Walk the plan's stages, proposing each delete in dependency order.

        ``dry_run=True`` records what *would* be proposed without calling the
        Broker at all (a second dry-run layer above the Broker's own LIVE_MODE).
        ``prior`` lets a re-run skip resources already finished.
        """
        result = ExecutionResult(correlation_id=plan.correlation_id, dry_run=dry_run)
        done = _finished_ids(prior)
        item_by_id = {i.resource.resource_id: i for i in plan.items}
        total_delete = plan.to_delete

        for stage in plan.stages:
            stage_complete = True
            for rid in stage.resource_ids:
                item = item_by_id[rid]
                if rid in done:
                    result.records.append(self._skip(item, "already completed in a prior run"))
                    continue
                record = self._propose_one(item, plan, total_delete=total_delete, dry_run=dry_run)
                result.records.append(record)
                if record.status not in _DONE_STATUSES and not (
                    dry_run and record.status == "proposed"
                ):
                    stage_complete = False

            if self._halt_on_incomplete_stage and not stage_complete:
                result.halted = True
                result.halt_reason = (
                    f"stage {stage.index} did not fully complete; "
                    "later stages may depend on it — resolve and re-run"
                )
                self._mark_remaining_skipped(plan, stage.index, result, item_by_id)
                break

        result.finished_at = self._now_fn().isoformat()
        _tally(result)
        logger.info(
            "executor.execute: correlation=%s dry_run=%s executed=%d pending=%d denied=%d failed=%d halted=%s",
            plan.correlation_id,
            dry_run,
            result.executed,
            result.pending_approval,
            result.denied,
            result.failed,
            result.halted,
        )
        return result

    # ------------------------------------------------------------------ #
    # Per-resource proposal
    # ------------------------------------------------------------------ #

    def _propose_one(
        self, item: PlanItem, plan: DecommissionPlan, *, total_delete: int, dry_run: bool
    ) -> ExecutionRecord:
        action_class = item.action_class or "decommission.delete_resource"
        target = self._target(item)
        params = self._params(item, action_class, total_delete=total_delete)
        idem = f"{plan.correlation_id}:{action_class}:{item.resource.resource_id}"

        record = ExecutionRecord(
            resource_id=item.resource.resource_id,
            action_class=action_class,
            target=target,
            status="proposed",
            stage=item.stage,
            idempotency_key=idem,
            started_at=self._now_fn().isoformat(),
        )

        if dry_run:
            record.detail = "dry-run: Broker not called"
            record.finished_at = self._now_fn().isoformat()
            return record

        last_error: str | None = None
        for attempt in range(1, self._max_attempts + 1):
            record.attempts = attempt
            try:
                response = self._proposer(
                    action_class=action_class,
                    target=target,
                    params=params,
                    proposed_tier=item.proposed_tier or 3,
                    rationale=f"decommission: {item.reason} (risk={item.risk})",
                    correlation_id=plan.correlation_id,
                    environment=plan.environment,
                    requested_by=self._requested_by,
                )
            except Exception as exc:
                last_error = str(exc)
                category = _classify_error(last_error)
                if category == "transient" and attempt < self._max_attempts:
                    logger.warning(
                        "executor: transient error on %s (attempt %d/%d): %s",
                        item.resource.resource_id,
                        attempt,
                        self._max_attempts,
                        last_error,
                    )
                    continue
                record.status = "failed"
                record.error = f"{category}: {last_error}"
                record.finished_at = self._now_fn().isoformat()
                return record

            record.broker_status = str(response.get("status", "unknown"))
            record.status = _BROKER_STATUS_MAP.get(record.broker_status, "failed")
            record.detail = response.get("detail") or response.get("reason")
            record.finished_at = self._now_fn().isoformat()
            return record

        # Unreachable in practice (loop returns), but keeps the type checker happy.
        record.status = "failed"
        record.error = last_error
        return record

    def _target(self, item: PlanItem) -> dict[str, Any]:
        resource = item.resource
        return {
            "type": resource.type,
            "name": resource.name,
            "project": resource.project,
            "region": resource.location,
        }

    def _params(self, item: PlanItem, action_class: str, *, total_delete: int) -> dict[str, Any]:
        resource = item.resource
        if action_class == "terraform.destroy_target":
            return {
                "working_dir": self._tf_working_dir,
                "workspace": item.resource.environment or "default",
                "target_address": resource.terraform_address or "",
                "resource_id": resource.resource_id,
                "target_count": total_delete,
            }
        return {
            "asset_type": resource.type,
            "resource_name": resource.name,
            "resource_id": resource.resource_id,
            "project": resource.project,
            "location": resource.location,
            "target_count": total_delete,
        }

    def _skip(self, item: PlanItem, reason: str) -> ExecutionRecord:
        now = self._now_fn().isoformat()
        return ExecutionRecord(
            resource_id=item.resource.resource_id,
            action_class=item.action_class,
            status="skipped",
            stage=item.stage,
            detail=reason,
            started_at=now,
            finished_at=now,
        )

    def _mark_remaining_skipped(
        self,
        plan: DecommissionPlan,
        halted_stage: int,
        result: ExecutionResult,
        item_by_id: dict[str, PlanItem],
    ) -> None:
        already = {r.resource_id for r in result.records}
        for stage in plan.stages:
            if stage.index <= halted_stage:
                continue
            for rid in stage.resource_ids:
                if rid in already:
                    continue
                result.records.append(
                    self._skip(
                        item_by_id[rid], f"not attempted — campaign halted at stage {halted_stage}"
                    )
                )


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def _finished_ids(prior: ExecutionResult | None) -> set[str]:
    if prior is None:
        return set()
    return {r.resource_id for r in prior.records if r.status in _DONE_STATUSES}


def _classify_error(message: str) -> str:
    lowered = message.lower()
    if any(marker in lowered for marker in _PERMISSION_MARKERS):
        return "permission"
    if any(marker in lowered for marker in _DEPENDENCY_MARKERS):
        return "dependency_conflict"
    if any(marker in lowered for marker in _LOCKED_MARKERS):
        return "locked"
    if any(marker in lowered for marker in _TRANSIENT_MARKERS):
        return "transient"
    return "error"


def _tally(result: ExecutionResult) -> None:
    for record in result.records:
        if record.status in ("executed", "already_done"):
            result.executed += 1
        elif record.status == "pending_approval":
            result.pending_approval += 1
        elif record.status == "denied":
            result.denied += 1
        elif record.status == "failed":
            result.failed += 1
        elif record.status == "skipped":
            result.skipped += 1
