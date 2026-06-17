"""
Tests for main.py — the Action Broker HTTP surface (FastAPI).

This is the service's security boundary, so the focus is on the auth and
request-handling branches rather than the happy path alone:

- _verify_id_token: dry-run bypass, fail-closed when OIDC_AUDIENCE is unset in
  LIVE_MODE, missing/invalid Bearer token, and the verified-token success path.
- /healthz: liveness contract.
- /mcp/tools/list, /mcp/tools/call: tool catalogue, propose_action delegation,
  caller-identity defaulting, BrokerError -> 400, missing field -> 400,
  not_implemented tools, and unknown-tool -> 404.
- /pubsub/approved: push-token rejection, undecodable/invalid payload acking
  with 204, successful on_approval dispatch, and on_approval failure -> 500.

Everything runs with LIVE_MODE=false (the module import default), so no live
GCP clients are created. _verify_id_token's LIVE_MODE branches are exercised by
calling the helper directly with patched module globals — this avoids starting
the app's lifespan in live mode.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import main
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pubsub_envelope(payload: dict) -> dict:
    """Wrap a JSON payload the way Pub/Sub push delivers it."""
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data}}


def _valid_approval() -> dict:
    return {
        "action_id": "act_abc123",
        "approval_id": "apv_xyz",
        "decision": "approved",
        "approver_identity": ["operator@example.com"],
        "approved_at": datetime.now(tz=UTC).isoformat(),
    }


def _fake_request(headers: dict[str, str]) -> MagicMock:
    request = MagicMock()
    request.headers = headers
    return request


@pytest.fixture
def client_and_broker():
    """A TestClient with the broker in _state replaced by a MagicMock.

    The lifespan still runs (loading the real PolicyEngine), then we swap the
    broker so each test controls its return values deterministically.
    """
    with TestClient(main.app) as client:
        mock_broker = MagicMock()
        main._state["broker"] = mock_broker
        yield client, mock_broker


# ---------------------------------------------------------------------------
# _verify_id_token — auth boundary
# ---------------------------------------------------------------------------


class TestVerifyIdToken:
    async def test_dry_run_skips_verification(self) -> None:
        with patch.object(main, "LIVE_MODE", False):
            caller = await main._verify_id_token(_fake_request({}))
        assert caller == "dry-run@local"

    async def test_live_mode_without_audience_fails_closed(self) -> None:
        with (
            patch.object(main, "LIVE_MODE", True),
            patch.object(main, "OIDC_AUDIENCE", ""),
            pytest.raises(HTTPException) as exc_info,
        ):
            await main._verify_id_token(_fake_request({"Authorization": "Bearer x"}))
        assert exc_info.value.status_code == 500

    async def test_live_mode_missing_bearer_is_401(self) -> None:
        with (
            patch.object(main, "LIVE_MODE", True),
            patch.object(main, "OIDC_AUDIENCE", "https://broker.example"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await main._verify_id_token(_fake_request({}))
        assert exc_info.value.status_code == 401

    async def test_live_mode_valid_token_returns_email(self) -> None:
        with (
            patch.object(main, "LIVE_MODE", True),
            patch.object(main, "OIDC_AUDIENCE", "https://broker.example"),
            patch(
                "google.oauth2.id_token.verify_oauth2_token",
                return_value={"email": "caller@example.com"},
            ),
        ):
            caller = await main._verify_id_token(
                _fake_request({"Authorization": "Bearer good-token"})
            )
        assert caller == "caller@example.com"

    async def test_live_mode_invalid_token_is_401(self) -> None:
        with (
            patch.object(main, "LIVE_MODE", True),
            patch.object(main, "OIDC_AUDIENCE", "https://broker.example"),
            patch(
                "google.oauth2.id_token.verify_oauth2_token",
                side_effect=ValueError("bad signature"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await main._verify_id_token(_fake_request({"Authorization": "Bearer nope"}))
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------


class TestHealthz:
    def test_returns_ok(self, client_and_broker) -> None:
        client, _ = client_and_broker
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "live_mode": False}


# ---------------------------------------------------------------------------
# /mcp/tools/list
# ---------------------------------------------------------------------------


class TestMcpToolsList:
    def test_lists_the_tool_catalogue(self, client_and_broker) -> None:
        client, _ = client_and_broker
        resp = client.post("/mcp/tools/list", json={})
        assert resp.status_code == 200
        names = {tool["name"] for tool in resp.json()["tools"]}
        assert {"propose_action", "request_approval", "execute", "rollback", "status"} <= names


# ---------------------------------------------------------------------------
# /mcp/tools/call
# ---------------------------------------------------------------------------


class TestMcpToolsCallProposeAction:
    def _input(self, **overrides) -> dict:
        base = {
            "action_class": "cloud_run.scale_within_range",
            "target": {"type": "cloud_run", "name": "svc", "project": "proj"},
            "params": {"instances": 3},
            "requested_by": "agent@sa",
            "correlation_id": "corr-1",
            "environment": "dev",
        }
        base.update(overrides)
        return base

    def test_delegates_to_broker_and_returns_result(self, client_and_broker) -> None:
        client, broker = client_and_broker
        broker.propose_action.return_value = {"status": "pending_approval", "action_id": "act_1"}

        resp = client.post(
            "/mcp/tools/call", json={"name": "propose_action", "input": self._input()}
        )

        assert resp.status_code == 200
        text = resp.json()["content"][0]["text"]
        assert json.loads(text) == {"status": "pending_approval", "action_id": "act_1"}
        broker.propose_action.assert_called_once()

    def test_defaults_requested_by_to_caller_identity(self, client_and_broker) -> None:
        client, broker = client_and_broker
        broker.propose_action.return_value = {"status": "denied"}

        bare_input = self._input()
        del bare_input["requested_by"]
        client.post("/mcp/tools/call", json={"name": "propose_action", "input": bare_input})

        # requested_by omitted -> caller identity ("dry-run@local" in non-live mode)
        _, kwargs = broker.propose_action.call_args
        assert kwargs["requested_by"] == "dry-run@local"

    def test_broker_error_maps_to_400(self, client_and_broker) -> None:
        from broker import BrokerError

        client, broker = client_and_broker
        broker.propose_action.side_effect = BrokerError("Unknown action_class")

        resp = client.post(
            "/mcp/tools/call", json={"name": "propose_action", "input": self._input()}
        )
        assert resp.status_code == 400

    def test_missing_input_field_maps_to_400(self, client_and_broker) -> None:
        client, _ = client_and_broker
        bad_input = self._input()
        del bad_input["correlation_id"]

        resp = client.post(
            "/mcp/tools/call", json={"name": "propose_action", "input": bad_input}
        )
        assert resp.status_code == 400
        assert "Missing input field" in resp.json()["detail"]


class TestMcpToolsCallOtherTools:
    def test_request_approval_returns_not_implemented(self, client_and_broker) -> None:
        client, _ = client_and_broker
        resp = client.post(
            "/mcp/tools/call",
            json={"name": "request_approval", "input": {"action_id": "act_1"}},
        )
        assert resp.status_code == 200
        assert json.loads(resp.json()["content"][0]["text"])["status"] == "not_implemented"

    @pytest.mark.parametrize("tool", ["execute", "rollback", "status"])
    def test_stub_tools_return_not_implemented(self, client_and_broker, tool: str) -> None:
        client, _ = client_and_broker
        resp = client.post(
            "/mcp/tools/call", json={"name": tool, "input": {"action_id": "act_1"}}
        )
        assert resp.status_code == 200
        body = json.loads(resp.json()["content"][0]["text"])
        assert body == {"status": "not_implemented", "tool": tool}

    def test_unknown_tool_is_404(self, client_and_broker) -> None:
        client, _ = client_and_broker
        resp = client.post("/mcp/tools/call", json={"name": "definitely_not_a_tool", "input": {}})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /pubsub/approved
# ---------------------------------------------------------------------------


class TestPubsubApproved:
    def test_invalid_push_token_is_401(self, client_and_broker) -> None:
        client, broker = client_and_broker
        with patch.object(main, "PUBSUB_PUSH_TOKEN", "expected-secret"):
            resp = client.post(
                "/pubsub/approved",
                params={"token": "wrong"},
                json=_pubsub_envelope(_valid_approval()),
            )
        assert resp.status_code == 401
        broker.on_approval.assert_not_called()

    def test_valid_approval_dispatches_to_broker(self, client_and_broker) -> None:
        client, broker = client_and_broker
        resp = client.post("/pubsub/approved", json=_pubsub_envelope(_valid_approval()))
        assert resp.status_code == 204
        broker.on_approval.assert_called_once()

    def test_undecodable_payload_is_acked_without_dispatch(self, client_and_broker) -> None:
        client, broker = client_and_broker
        resp = client.post(
            "/pubsub/approved", json={"message": {"data": "not-valid-base64!!!"}}
        )
        # 204 ack avoids an infinite DLQ retry loop on a permanently-bad message.
        assert resp.status_code == 204
        broker.on_approval.assert_not_called()

    def test_schema_invalid_payload_is_acked_without_dispatch(self, client_and_broker) -> None:
        client, broker = client_and_broker
        resp = client.post(
            "/pubsub/approved", json=_pubsub_envelope({"not": "an approval"})
        )
        assert resp.status_code == 204
        broker.on_approval.assert_not_called()

    def test_on_approval_failure_is_500(self, client_and_broker) -> None:
        client, broker = client_and_broker
        broker.on_approval.side_effect = RuntimeError("firestore unavailable")
        resp = client.post("/pubsub/approved", json=_pubsub_envelope(_valid_approval()))
        assert resp.status_code == 500
