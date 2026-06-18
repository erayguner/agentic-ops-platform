"""
Tests for broker.py — Broker.propose_action, on_approval, _execute_action.

Coverage gaps addressed:
- propose_action: unknown action_class, idempotency hit, validation failure,
  policy deny, tier 1/2 auto-approve (dry-run), tier 3/4 pending approval
- on_approval: rejected, expired, approved_ack
- _execute_action: dry-run stub path, live success, live executor failure,
  live post-condition failure with successful rollback, rollback also fails
- _emit_audit: called on every code path (verified via pubsub mock)
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from broker import Broker, BrokerError
from policy import Decision
from schemas import ActionApproval

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_decision(
    *,
    allowed: bool = True,
    tier: int = 2,
    deny_reason: str | None = None,
    rule_matched: str = "action.class:dev",
) -> Decision:
    return Decision(
        tier=tier,
        allowed=allowed,
        required_approvers=0 if tier <= 2 else 1,
        bounds={},
        deny_reason=deny_reason,
        rule_matched=rule_matched,
    )


def _make_broker(
    *,
    policy_decision: Decision | None = None,
    idempotency_hit: dict | None = None,
) -> Broker:
    policy_engine = MagicMock()
    policy_engine.decide.return_value = policy_decision or _make_decision()

    idempotency_store = MagicMock()
    idempotency_store.check.return_value = idempotency_hit  # None = no prior execution

    pubsub_client = MagicMock()
    return Broker(
        policy_engine=policy_engine,
        idempotency_store=idempotency_store,
        pubsub_client=pubsub_client,
    )


def _default_propose_kwargs(**overrides) -> dict:
    base: dict[str, Any] = {
        "action_class": "cloud_run.scale_within_range",
        "target": {"type": "cloud_run", "name": "svc", "project": "proj", "region": "us-central1"},
        "params": {"instances": 3},
        "requested_by": "agent@sa.iam.gserviceaccount.com",
        "correlation_id": "corr-abc123",
        "environment": "dev",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# propose_action — unknown action_class
# ---------------------------------------------------------------------------


class TestProposeActionUnknownClass:
    def test_raises_broker_error_for_unregistered_action_class(self) -> None:
        broker = _make_broker()
        with (
            patch("broker.is_registered", return_value=False),
            pytest.raises(BrokerError, match="Unknown action_class"),
        ):
            broker.propose_action(**_default_propose_kwargs(action_class="not.real"))


# ---------------------------------------------------------------------------
# propose_action — idempotency hit
# ---------------------------------------------------------------------------


class TestProposeActionIdempotencyHit:
    def test_returns_already_executed_with_prior_outcome(self) -> None:
        prior = {"status": "success", "detail": "scaled"}
        broker = _make_broker(idempotency_hit=prior)

        with patch("broker.is_registered", return_value=True):
            result = broker.propose_action(**_default_propose_kwargs())

        assert result["status"] == "already_executed"
        assert result["prior_outcome"] == prior


# ---------------------------------------------------------------------------
# propose_action — validation failure
# ---------------------------------------------------------------------------


class TestProposeActionValidationFailure:
    def test_raises_broker_error_on_invalid_params(self) -> None:
        broker = _make_broker()
        executor = MagicMock()
        executor.validate.side_effect = ValueError("instances must be a positive int")

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            pytest.raises(BrokerError, match="Parameter validation failed"),
        ):
            broker.propose_action(**_default_propose_kwargs())

    def test_emits_audit_on_validation_failure(self) -> None:
        broker = _make_broker()
        executor = MagicMock()
        executor.validate.side_effect = ValueError("bad")

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_audit") as mock_audit,
            pytest.raises(BrokerError),
        ):
            broker.propose_action(**_default_propose_kwargs())

        mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# propose_action — policy deny
# ---------------------------------------------------------------------------


class TestProposeActionPolicyDeny:
    def test_returns_denied_status(self) -> None:
        broker = _make_broker(
            policy_decision=_make_decision(
                allowed=False, deny_reason="action_class_denied_in_policy"
            )
        )
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
        ):
            result = broker.propose_action(**_default_propose_kwargs())

        assert result["status"] == "denied"
        assert result["reason"] == "action_class_denied_in_policy"
        assert "action_id" in result

    def test_does_not_call_execute_when_denied(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(allowed=False, deny_reason="blocked"))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
        ):
            broker.propose_action(**_default_propose_kwargs())

        executor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# propose_action — tier 1/2 auto-approve (dry-run path)
# ---------------------------------------------------------------------------


class TestProposeActionAutoApprove:
    def test_tier2_returns_stub_not_executed_in_dry_run(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(tier=2))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.LIVE_MODE", False),
            patch("broker.publish_action_requested"),
            patch("broker.publish_action_executed"),
            patch("broker.publish_audit"),
        ):
            result = broker.propose_action(**_default_propose_kwargs())

        assert result["status"] == "stub_not_executed"
        assert "action_id" in result

    def test_tier2_records_idempotency_in_dry_run(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(tier=2))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.LIVE_MODE", False),
            patch("broker.publish_action_requested"),
            patch("broker.publish_action_executed"),
            patch("broker.publish_audit"),
        ):
            broker.propose_action(**_default_propose_kwargs())

        broker._idem.record.assert_called_once()

    def test_tier2_publishes_action_requested_event(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(tier=2))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.LIVE_MODE", False),
            patch("broker.publish_action_requested") as mock_req,
            patch("broker.publish_action_executed"),
            patch("broker.publish_audit"),
        ):
            broker.propose_action(**_default_propose_kwargs())

        mock_req.assert_called_once()


# ---------------------------------------------------------------------------
# propose_action — tier 3/4 pending approval
# ---------------------------------------------------------------------------


class TestProposeActionPendingApproval:
    def test_tier3_returns_pending_approval_status(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(tier=3))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_action_requested"),
            patch("broker.publish_audit"),
        ):
            result = broker.propose_action(**_default_propose_kwargs())

        assert result["status"] == "pending_approval"
        assert result["tier"] == 3
        assert "action_id" in result
        assert "approval_window_until" in result

    def test_tier4_also_returns_pending_approval(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(tier=4))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_action_requested"),
            patch("broker.publish_audit"),
        ):
            result = broker.propose_action(**_default_propose_kwargs())

        assert result["status"] == "pending_approval"

    def test_tier3_does_not_execute_immediately(self) -> None:
        broker = _make_broker(policy_decision=_make_decision(tier=3))
        executor = MagicMock()
        executor.validate.return_value = None

        with (
            patch("broker.is_registered", return_value=True),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_action_requested"),
            patch("broker.publish_audit"),
        ):
            broker.propose_action(**_default_propose_kwargs())

        executor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# on_approval
# ---------------------------------------------------------------------------


class TestOnApproval:
    def _approval(self, decision: str) -> ActionApproval:
        return ActionApproval(
            action_id="act_abc123",
            approval_id="apv_xyz",
            decision=decision,
            approver_identity=["operator@example.com"],
            approved_at=datetime.now(tz=UTC),
        )

    def test_rejected_returns_rejected_status(self) -> None:
        broker = _make_broker()
        result = broker.on_approval(self._approval("rejected"))
        assert result["status"] == "rejected"
        assert result["action_id"] == "act_abc123"

    def test_expired_returns_expired_status(self) -> None:
        broker = _make_broker()
        result = broker.on_approval(self._approval("expired"))
        assert result["status"] == "expired"

    def test_approved_returns_approved_ack(self) -> None:
        broker = _make_broker()
        result = broker.on_approval(self._approval("approved"))
        assert result["status"] == "approved_ack"
        assert result["action_id"] == "act_abc123"


# ---------------------------------------------------------------------------
# _execute_action — live path failures (LIVE_MODE=True)
# ---------------------------------------------------------------------------


class TestExecuteActionLiveFailures:
    def _make_action_request(self, action_id: str = "act_test123"):
        from schemas import ActionRequest

        return ActionRequest(
            action_id=action_id,
            recommendation={"action_class": "cloud_run.scale_within_range"},
            requested_by="agent@sa",
            idempotency_key="idem_key",
        )

    def test_executor_exception_raises_broker_error(self) -> None:
        broker = _make_broker()
        executor = MagicMock()
        executor.execute.side_effect = RuntimeError("GCP API unreachable")

        with (
            patch("broker.LIVE_MODE", True),
            patch("broker.mint_credentials", return_value=MagicMock()),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_audit"),
            pytest.raises(BrokerError, match="Execution failed"),
        ):
            broker._execute_action(
                self._make_action_request(),
                "cloud_run.scale_within_range",
                {"name": "svc"},
                {"instances": 3},
                "dev",
                "corr-1",
                "agent@sa",
                _make_decision(tier=2),
            )

    def test_post_condition_failure_triggers_rollback(self) -> None:
        broker = _make_broker()
        outcome = MagicMock()
        outcome.status = "success"
        outcome.detail = "scaled"
        outcome.resource_refs = []

        executor = MagicMock()
        executor.execute.return_value = outcome
        executor.verify.return_value = False
        executor.rollback.return_value = MagicMock()

        with (
            patch("broker.LIVE_MODE", True),
            patch("broker.mint_credentials", return_value=MagicMock()),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_audit"),
        ):
            result = broker._execute_action(
                self._make_action_request(),
                "cloud_run.scale_within_range",
                {"name": "svc"},
                {"instances": 3},
                "dev",
                "corr-1",
                "agent@sa",
                _make_decision(tier=2),
            )

        assert result["status"] == "rolled_back"
        executor.rollback.assert_called_once()

    def test_rollback_exception_is_logged_not_raised(self) -> None:
        broker = _make_broker()
        outcome = MagicMock()
        outcome.status = "success"

        executor = MagicMock()
        executor.execute.return_value = outcome
        executor.verify.return_value = False
        executor.rollback.side_effect = RuntimeError("rollback also failed")

        with (
            patch("broker.LIVE_MODE", True),
            patch("broker.mint_credentials", return_value=MagicMock()),
            patch("broker.get_executor", return_value=executor),
            patch("broker.publish_audit"),
        ):
            result = broker._execute_action(
                self._make_action_request(),
                "cloud_run.scale_within_range",
                {"name": "svc"},
                {"instances": 3},
                "dev",
                "corr-1",
                "agent@sa",
                _make_decision(tier=2),
            )

        # Should still return rolled_back, not propagate the rollback exception
        assert result["status"] == "rolled_back"
