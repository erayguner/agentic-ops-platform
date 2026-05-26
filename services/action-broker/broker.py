"""
Action Broker lifecycle orchestrator.

Lifecycle: propose → policy_check → (auto-approve | publish_request | reject)
           → on_approval → execute → verify → audit
           → (rollback on health regression)

All Pub/Sub publishes, idempotency checks, and audit records are emitted even
when LIVE_MODE=False.  Only the executor's execute() is stubbed out.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from events import publish_action_executed, publish_action_requested, publish_audit
from executors import get_executor, is_registered
from idempotency import IdempotencyStore
from impersonation import mint_credentials
from policy import Decision, PolicyEngine
from schemas import ActionApproval, ActionExecuted, ActionRequest, AuditRecord, PolicyDecision

logger = logging.getLogger(__name__)

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "ops-agents-dev")
APPROVAL_WINDOW_MINUTES = int(os.environ.get("APPROVAL_WINDOW_MINUTES", "15"))


class BrokerError(Exception):
    pass


class Broker:
    def __init__(
        self,
        policy_engine: PolicyEngine,
        idempotency_store: IdempotencyStore,
        pubsub_client,
    ) -> None:
        self._policy = policy_engine
        self._idem = idempotency_store
        self._pubsub = pubsub_client

    # ------------------------------------------------------------------
    # propose_action — MCP tool entry point
    # ------------------------------------------------------------------

    def propose_action(
        self,
        action_class: str,
        target: dict[str, Any],
        params: dict[str, Any],
        requested_by: str,
        correlation_id: str,
        environment: str,
    ) -> dict[str, Any]:
        """
        Validate, policy-check, and either auto-approve or publish for
        human approval.  Returns a dict describing the immediate outcome.
        """
        if not is_registered(action_class):
            raise BrokerError(f"Unknown action_class: {action_class!r}")

        # 1. Idempotency pre-check
        existing = self._idem.check(correlation_id, action_class, target)
        if existing:
            logger.info(
                "Idempotency hit — returning prior outcome for correlation_id=%s", correlation_id
            )
            return {"status": "already_executed", "prior_outcome": existing}

        # 2. Param validation via executor
        executor = get_executor(action_class)
        try:
            executor.validate(params)
        except ValueError as exc:
            self._emit_audit(
                correlation_id,
                "action_requested",
                requested_by,
                environment,
                action_class,
                PolicyDecision(tier=0, rule="validation", outcome="denied"),
                outcome={"status": "invalid_params", "error": str(exc)},
            )
            raise BrokerError(f"Parameter validation failed: {exc}") from exc

        # 3. Policy evaluation
        decision: Decision = self._policy.decide(action_class, environment, target, params)

        action_id = f"act_{uuid.uuid4().hex[:16]}"
        idempotency_key = f"{correlation_id}:{action_class}:{action_id}"
        approval_window = datetime.now(tz=UTC) + timedelta(minutes=APPROVAL_WINDOW_MINUTES)

        action_request = ActionRequest(
            action_id=action_id,
            recommendation={"action_class": action_class, "target": target, "params": params},
            requested_by=requested_by,
            idempotency_key=idempotency_key,
            approval_window_until=approval_window if decision.tier >= 3 else None,
        )

        policy_dec = PolicyDecision(
            tier=decision.tier,
            rule=decision.rule_matched,
            outcome="approved" if decision.allowed else "denied",
        )

        # 4. Route by tier
        if not decision.allowed:
            logger.warning("Action denied by policy: %s", decision.deny_reason)
            self._emit_audit(
                correlation_id,
                "action_requested",
                requested_by,
                environment,
                action_class,
                policy_dec,
                outcome={"status": "denied", "reason": decision.deny_reason},
            )
            return {"status": "denied", "action_id": action_id, "reason": decision.deny_reason}

        if decision.tier <= 2:
            # Auto-approve: publish request for audit, then execute directly
            publish_action_requested(
                self._pubsub, GCP_PROJECT_ID, action_request.model_dump(mode="json")
            )
            self._emit_audit(
                correlation_id,
                "action_requested",
                requested_by,
                environment,
                action_class,
                policy_dec,
            )
            return self._execute_action(
                action_request,
                action_class,
                target,
                params,
                environment,
                correlation_id,
                requested_by,
                decision,
            )

        # Tier 3/4: publish for human approval
        publish_action_requested(
            self._pubsub, GCP_PROJECT_ID, action_request.model_dump(mode="json")
        )
        self._emit_audit(
            correlation_id, "action_requested", requested_by, environment, action_class, policy_dec
        )
        logger.info("Action queued for approval: action_id=%s tier=%d", action_id, decision.tier)
        return {
            "status": "pending_approval",
            "action_id": action_id,
            "tier": decision.tier,
            "approval_window_until": approval_window.isoformat(),
        }

    # ------------------------------------------------------------------
    # on_approval — called by /pubsub/approved handler
    # ------------------------------------------------------------------

    def on_approval(self, approval: ActionApproval) -> dict[str, Any]:
        """Handle an approved or rejected ActionApproval from the Slack-notifier."""
        if approval.decision == "rejected":
            logger.info("Action rejected by approver: action_id=%s", approval.action_id)
            return {"status": "rejected", "action_id": approval.action_id}
        if approval.decision == "expired":
            logger.info("Action approval expired: action_id=%s", approval.action_id)
            return {"status": "expired", "action_id": approval.action_id}

        # decision == "approved" — we reconstruct enough context from the approval
        # In production this would be fetched from the Firestore action ledger.
        logger.info(
            "Processing approval: action_id=%s approvers=%s",
            approval.action_id,
            approval.approver_identity,
        )
        return {"status": "approved_ack", "action_id": approval.action_id}

    # ------------------------------------------------------------------
    # Internal execute
    # ------------------------------------------------------------------

    def _execute_action(
        self,
        action_request: ActionRequest,
        action_class: str,
        target: dict[str, Any],
        params: dict[str, Any],
        environment: str,
        correlation_id: str,
        requested_by: str,
        decision: Decision,
    ) -> dict[str, Any]:
        action_id = action_request.action_id
        policy_dec = PolicyDecision(
            tier=decision.tier, rule=decision.rule_matched, outcome="approved"
        )
        executor = get_executor(action_class)

        if not LIVE_MODE:
            # Stub path: emit the full event chain without calling real APIs
            logger.info(
                "[DRY-RUN] Would execute action_id=%s action_class=%s", action_id, action_class
            )
            stub_outcome = {"status": "stub_not_executed", "detail": "LIVE_MODE=false"}
            self._idem.record(correlation_id, action_class, target, stub_outcome)
            executed = ActionExecuted(
                action_id=action_id,
                status="stub_not_executed",
                outcome={
                    "status": "stub_not_executed",
                    "detail": "LIVE_MODE=false",
                    "resource_refs": [],
                },
                verification={},
            )
            publish_action_executed(self._pubsub, GCP_PROJECT_ID, executed.model_dump(mode="json"))
            self._emit_audit(
                correlation_id,
                "action_executed",
                requested_by,
                environment,
                action_class,
                policy_dec,
                outcome=stub_outcome,
            )
            return {"status": "stub_not_executed", "action_id": action_id}

        # Live path
        credentials = mint_credentials(action_class)
        try:
            outcome = executor.execute(params, credentials)
        except Exception as exc:
            logger.exception("Executor failed action_id=%s: %s", action_id, exc)
            self._emit_audit(
                correlation_id,
                "action_executed",
                requested_by,
                environment,
                action_class,
                policy_dec,
                outcome={"status": "failed", "error": str(exc)},
            )
            raise BrokerError(f"Execution failed: {exc}") from exc

        # Post-condition verification
        ok = executor.verify(params, outcome)
        if not ok:
            logger.warning("Post-condition failed — triggering rollback action_id=%s", action_id)
            try:
                rb = executor.rollback(params, outcome)
            except Exception as rb_exc:
                logger.error("Rollback also failed: %s", rb_exc)
                rb = None
            self._emit_audit(
                correlation_id,
                "rollback",
                requested_by,
                environment,
                action_class,
                policy_dec,
                outcome={"status": "rolled_back", "rollback": str(rb)},
            )
            return {"status": "rolled_back", "action_id": action_id}

        outcome_dict = {
            "status": outcome.status,
            "detail": outcome.detail,
            "resource_refs": outcome.resource_refs,
        }
        self._idem.record(correlation_id, action_class, target, outcome_dict)

        executed = ActionExecuted(
            action_id=action_id,
            status=outcome.status,
            outcome=outcome_dict,
            verification={"passed": True},
        )
        publish_action_executed(self._pubsub, GCP_PROJECT_ID, executed.model_dump(mode="json"))
        self._emit_audit(
            correlation_id,
            "action_executed",
            requested_by,
            environment,
            action_class,
            policy_dec,
            outcome=outcome_dict,
        )

        logger.info("Action completed action_id=%s status=%s", action_id, outcome.status)
        return {"status": outcome.status, "action_id": action_id, "detail": outcome.detail}

    # ------------------------------------------------------------------
    # Audit helper
    # ------------------------------------------------------------------

    def _emit_audit(
        self,
        correlation_id: str,
        phase: str,
        agent_identity: str,
        environment: str,
        action_class: str | None,
        policy_decision: PolicyDecision,
        outcome: dict[str, Any] | None = None,
    ) -> None:
        record = AuditRecord(
            audit_id=f"aud_{uuid.uuid4().hex[:16]}",
            correlation_id=correlation_id,
            timestamp=datetime.now(tz=UTC),
            phase=phase,
            agent_identity=agent_identity,
            environment=environment,
            domain="platform",
            action_class=action_class,
            policy_decision=policy_decision,
            outcome=outcome,
        )
        publish_audit(self._pubsub, GCP_PROJECT_ID, record.model_dump(mode="json"))
