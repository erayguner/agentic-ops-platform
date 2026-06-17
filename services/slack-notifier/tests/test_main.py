"""
Tests for main.py — the Slack-notifier HTTP surface (FastAPI).

Covers the two request paths plus health:

- /healthz: liveness contract.
- /pubsub/push: push-token rejection, undecodable/invalid payload acking with
  204 (avoid DLQ loops), successful delivery dispatch, and a transient delivery
  failure surfacing as 500 (so Pub/Sub retries).
- /slack/interactivity: signature verification is delegated to
  verify_slack_signature; here we patch it and exercise the form-parse success
  path, the delegation to handle_block_actions, and the malformed-body -> 400
  branch.

Everything runs with LIVE_SLACK_ENABLED=false (module import default), so the
lifespan creates no Slack/Pub/Sub clients. The collaborators
(deliver_notification, handle_block_actions, verify_slack_signature) are patched
on the main module so no real Slack calls are made.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import main
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pubsub_envelope(payload: dict) -> dict:
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    return {"message": {"data": data}}


def _valid_notification() -> dict:
    return {
        "schema": "ops.notification.v1",
        "notification_id": "ntf_1",
        "correlation_id": "corr_1",
        "produced_at": datetime.now(tz=UTC).isoformat(),
        "severity": "high",
        "environment": "dev",
        "domain": "sre",
        "summary": "Cloud Run service is returning elevated 5xx errors",
        "affected_component": {"type": "cloud_run", "name": "svc", "project": "proj"},
        "impact": "Checkout requests are failing for a subset of users",
        "recommended_actions": [
            {
                "id": "a1",
                "label": "Roll back to previous revision",
                "action_class": "cloud_run.rollback_to_previous",
                "tier": 3,
                "reversible": True,
            }
        ],
        "human_required": True,
        "references": {},
        "agent": {"identity": "sre@sa", "model": "gemini"},
    }


@pytest.fixture
def client() -> TestClient:
    with TestClient(main.app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------


class TestHealthz:
    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "live_slack": False}


# ---------------------------------------------------------------------------
# /pubsub/push
# ---------------------------------------------------------------------------


class TestPubsubPush:
    def test_invalid_push_token_is_401(self, client: TestClient) -> None:
        with (
            patch.object(main, "PUBSUB_PUSH_TOKEN", "expected-secret"),
            patch.object(main, "deliver_notification", new=AsyncMock()) as deliver,
        ):
            resp = client.post(
                "/pubsub/push",
                params={"token": "wrong"},
                json=_pubsub_envelope(_valid_notification()),
            )
        assert resp.status_code == 401
        deliver.assert_not_awaited()

    def test_valid_notification_is_delivered(self, client: TestClient) -> None:
        with patch.object(main, "deliver_notification", new=AsyncMock()) as deliver:
            resp = client.post("/pubsub/push", json=_pubsub_envelope(_valid_notification()))
        assert resp.status_code == 204
        deliver.assert_awaited_once()

    def test_undecodable_payload_is_acked_without_delivery(self, client: TestClient) -> None:
        with patch.object(main, "deliver_notification", new=AsyncMock()) as deliver:
            resp = client.post("/pubsub/push", json={"message": {"data": "not-base64!!!"}})
        assert resp.status_code == 204
        deliver.assert_not_awaited()

    def test_schema_invalid_payload_is_acked_without_delivery(self, client: TestClient) -> None:
        with patch.object(main, "deliver_notification", new=AsyncMock()) as deliver:
            resp = client.post("/pubsub/push", json=_pubsub_envelope({"bad": "payload"}))
        assert resp.status_code == 204
        deliver.assert_not_awaited()

    def test_delivery_failure_is_500_for_retry(self, client: TestClient) -> None:
        failing = AsyncMock(side_effect=RuntimeError("slack 503"))
        with patch.object(main, "deliver_notification", new=failing):
            resp = client.post("/pubsub/push", json=_pubsub_envelope(_valid_notification()))
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# /slack/interactivity
# ---------------------------------------------------------------------------


class TestSlackInteractivity:
    def test_verified_request_delegates_to_handler(self, client: TestClient) -> None:
        payload = json.dumps({"actions": [{"action_id": "approve"}]})
        raw_body = f"payload={payload}".encode()

        with (
            patch.object(main, "verify_slack_signature", new=AsyncMock(return_value=raw_body)),
            patch.object(
                main, "handle_block_actions", new=AsyncMock(return_value={"ok": True})
            ) as handler,
        ):
            resp = client.post("/slack/interactivity", content=raw_body)

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        handler.assert_awaited_once()
        # The url-decoded payload JSON is forwarded to the handler.
        _, kwargs = handler.call_args
        assert kwargs["raw_payload"] == payload

    def test_signature_failure_propagates(self, client: TestClient) -> None:
        rejecting = AsyncMock(side_effect=HTTPException(status_code=403, detail="bad sig"))
        with (
            patch.object(main, "verify_slack_signature", new=rejecting),
            patch.object(main, "handle_block_actions", new=AsyncMock()) as handler,
        ):
            resp = client.post("/slack/interactivity", content=b"payload=%7B%7D")
        assert resp.status_code == 403
        handler.assert_not_awaited()

    def test_undecodable_body_is_400(self, client: TestClient) -> None:
        # verify returns bytes that cannot be UTF-8 decoded -> parse failure -> 400.
        bad_body = AsyncMock(return_value=b"\xff\xfe\xff")
        with (
            patch.object(main, "verify_slack_signature", new=bad_body),
            patch.object(main, "handle_block_actions", new=AsyncMock()) as handler,
        ):
            resp = client.post("/slack/interactivity", content=b"whatever")
        assert resp.status_code == 400
        handler.assert_not_awaited()
