"""aop_decommission.campaign — the end-to-end decommission lifecycle.

Wires the engine modules into the full campaign and is the seam the ADK
WorkflowAgent graph (``agent.py``) drives:

    discover → inventory → plan → [execute → re-scan → validate] → report

The default mode is ``plan`` — a non-destructive dry run that produces the plan
and a report and touches nothing. ``execute`` is opt-in and still flows through
every downstream gate: the executor only *proposes* to the Action Broker, the
Broker policy-gates and (for prod destroys) routes to human approval, and its
executors stay inert until ``LIVE_MODE=true``. An :class:`AuditSink` is invoked
at each phase so the campaign lands an immutable trail on ``ops.audit`` exactly
like every other AOP agent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from aop_decommission.executor import DecommissionExecutor
from aop_decommission.exemptions import ExemptionPolicy
from aop_decommission.inventory import InventoryScanner
from aop_decommission.planner import Planner
from aop_decommission.report import build_report, render_markdown
from aop_decommission.schemas import (
    DecommissionPlan,
    DecommissionReport,
    ExecutionResult,
    Inventory,
    ValidationResult,
)
from aop_decommission.validation import Validator

logger = logging.getLogger(__name__)

CampaignMode = Literal["plan", "execute"]

# (phase, payload) — phase is one of the AuditRecord lifecycle phases.
AuditSink = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class CampaignOutcome:
    """Everything the campaign produced, in one returnable bundle."""

    pre_inventory: Inventory
    plan: DecommissionPlan
    report: DecommissionReport
    execution: ExecutionResult | None = None
    post_inventory: Inventory | None = None
    validation: ValidationResult | None = None

    def report_markdown(self) -> str:
        return render_markdown(self.report, plan=self.plan)


class DecommissionCampaign:
    """Runs the full discover → plan → execute → validate → report lifecycle."""

    def __init__(
        self,
        *,
        scanner: InventoryScanner,
        policy: ExemptionPolicy,
        planner: Planner,
        executor: DecommissionExecutor | None = None,
        validator: Validator | None = None,
        correlation_id: str,
        project: str,
        environment: str,
        preservation_required: set[str] | None = None,
        audit: AuditSink | None = None,
    ) -> None:
        self._scanner = scanner
        self._policy = policy
        self._planner = planner
        self._executor = executor
        self._validator = validator or Validator()
        self._correlation_id = correlation_id
        self._project = project
        self._environment = environment
        self._preservation_required = preservation_required
        self._audit: AuditSink = audit or (lambda _phase, _payload: None)

    def run(
        self,
        *,
        mode: CampaignMode = "plan",
        broker_dry_run: bool = False,
        prior: ExecutionResult | None = None,
    ) -> CampaignOutcome:
        """Execute the campaign. ``mode='plan'`` (default) is non-destructive.

        Args:
            mode: ``plan`` produces the dry-run plan + report only; ``execute``
                additionally proposes teardown to the Broker, re-scans, validates.
            broker_dry_run: In ``execute`` mode, record proposals without calling
                the Broker — a rehearsal layer above the Broker's own LIVE_MODE.
            prior: A previous ExecutionResult so a re-run resumes (idempotency).
        """
        pre = self._scanner.scan(project=self._project, environment=self._environment)
        self._audit("finding", {"phase": "inventory", "resources": pre.count})

        plan = self._planner.plan(
            pre.resources,
            self._policy,
            correlation_id=self._correlation_id,
            project=self._project,
            environment=self._environment,
        )
        self._audit(
            "recommendation",
            {
                "phase": "plan",
                "to_delete": plan.to_delete,
                "retained_exempt": plan.retained_exempt,
                "manual_review": plan.manual_review,
                "irreversible": plan.irreversible,
            },
        )

        if mode == "plan":
            report = build_report(plan=plan, initial_count=pre.count, mode="plan")
            logger.info("campaign.run: plan-only complete project=%s", self._project)
            return CampaignOutcome(pre_inventory=pre, plan=plan, report=report)

        if self._executor is None:
            raise ValueError("mode='execute' requires an executor")

        execution = self._executor.execute(plan, dry_run=broker_dry_run, prior=prior)
        self._audit(
            "action_executed",
            {
                "phase": "execute",
                "executed": execution.executed,
                "pending_approval": execution.pending_approval,
                "failed": execution.failed,
                "denied": execution.denied,
                "halted": execution.halted,
            },
        )

        post = self._scanner.scan(project=self._project, environment=self._environment)
        validation = self._validator.validate(
            plan=plan,
            post_inventory=post,
            preservation_required=self._preservation_required,
        )
        self._audit(
            "finding",
            {"phase": "validation", "closure_ready": validation.closure_ready},
        )

        report = build_report(
            plan=plan,
            initial_count=pre.count,
            mode="execute",
            execution=execution,
            validation=validation,
        )
        logger.info(
            "campaign.run: execute complete project=%s closure_ready=%s",
            self._project,
            report.closure_ready,
        )
        return CampaignOutcome(
            pre_inventory=pre,
            plan=plan,
            report=report,
            execution=execution,
            post_inventory=post,
            validation=validation,
        )
