"""
Tests for signature.py — verify_slack_signature.

Coverage gaps addressed:
- Missing X-Slack-Request-Timestamp or X-Slack-Signature headers → 401
- Non-integer timestamp header → 401
- Timestamp outside ±5min replay window → 403
- Valid signature → returns body bytes
- Invalid signature (wrong HMAC) → 403
- Missing SLACK_SIGNING_SECRET env var → RuntimeError
- Edge: timestamp exactly at boundary (within and outside window)
"""

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from signature import _REPLAY_WINDOW_SECONDS, verify_slack_signature

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    body: bytes = b"payload=test",
    timestamp: str | None = None,
    signature: str | None = None,
    secret: str = "test-signing-secret",
) -> MagicMock:
    """
    Build a mock FastAPI Request with the given Slack signature headers.
    If signature is not provided, a valid one is computed from body + timestamp.
    """
    ts = timestamp or str(int(time.time()))
    if signature is None:
        basestring = f"v0:{ts}:{body.decode()}".encode()
        computed = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
        sig = computed
    else:
        sig = signature

    headers: dict = {}
    headers["X-Slack-Request-Timestamp"] = ts
    headers["X-Slack-Signature"] = sig

    request = MagicMock()
    request.headers = headers
    request.body = AsyncMock(return_value=body)
    return request


def _make_request_missing_headers(*, drop_timestamp=False, drop_signature=False) -> MagicMock:
    headers = {
        "X-Slack-Request-Timestamp": str(int(time.time())),
        "X-Slack-Signature": "v0=abc",
    }
    if drop_timestamp:
        headers.pop("X-Slack-Request-Timestamp")
    if drop_signature:
        headers.pop("X-Slack-Signature")

    request = MagicMock()
    request.headers = headers
    request.body = AsyncMock(return_value=b"body")
    return request


# ---------------------------------------------------------------------------
# Missing / malformed headers
# ---------------------------------------------------------------------------


class TestMissingHeaders:
    @pytest.mark.asyncio
    async def test_missing_timestamp_raises_401(self) -> None:
        req = _make_request_missing_headers(drop_timestamp=True)
        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "secret"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_signature_raises_401(self) -> None:
        req = _make_request_missing_headers(drop_signature=True)
        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "secret"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_integer_timestamp_raises_401(self) -> None:
        req = _make_request_missing_headers()
        req.headers["X-Slack-Request-Timestamp"] = "not-a-number"
        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "secret"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Replay-attack window
# ---------------------------------------------------------------------------


class TestReplayWindow:
    @pytest.mark.asyncio
    async def test_timestamp_too_old_raises_403(self) -> None:
        old_ts = str(int(time.time()) - _REPLAY_WINDOW_SECONDS - 1)
        req = _make_request(timestamp=old_ts)
        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "test-signing-secret"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_timestamp_too_new_raises_403(self) -> None:
        future_ts = str(int(time.time()) + _REPLAY_WINDOW_SECONDS + 1)
        req = _make_request(timestamp=future_ts)
        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "test-signing-secret"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_timestamp_at_exact_boundary_passes(self) -> None:
        # Exactly at the window boundary should still pass (abs diff == WINDOW)
        ts = str(int(time.time()) - _REPLAY_WINDOW_SECONDS)
        req = _make_request(timestamp=ts)
        with patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "test-signing-secret"}):
            result = await verify_slack_signature(req)
        assert result == b"payload=test"


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


class TestSignatureVerification:
    @pytest.mark.asyncio
    async def test_valid_signature_returns_body(self) -> None:
        body = b"payload=action%3Dapprove"
        req = _make_request(body=body)
        with patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "test-signing-secret"}):
            result = await verify_slack_signature(req)
        assert result == body

    @pytest.mark.asyncio
    async def test_wrong_signature_raises_403(self) -> None:
        req = _make_request(signature="v0=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef1234")
        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "test-signing-secret"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tampered_body_raises_403(self) -> None:
        # Sign with original body, then present different body
        secret = "test-signing-secret"
        original_body = b"payload=original"
        ts = str(int(time.time()))
        basestring = f"v0:{ts}:{original_body.decode()}".encode()
        sig = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()

        # Now claim a different body
        req = MagicMock()
        req.headers = {
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        }
        req.body = AsyncMock(return_value=b"payload=tampered")

        with (
            patch.dict("os.environ", {"SLACK_SIGNING_SECRET": secret}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await verify_slack_signature(req)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Missing env var
# ---------------------------------------------------------------------------


class TestMissingSigningSecret:
    @pytest.mark.asyncio
    async def test_missing_signing_secret_raises_runtime_error(self) -> None:
        req = _make_request()
        with patch.dict("os.environ", {}, clear=True):
            if "SLACK_SIGNING_SECRET" in __import__("os").environ:
                pytest.skip("SLACK_SIGNING_SECRET is set in environment")
            with pytest.raises(RuntimeError, match="SLACK_SIGNING_SECRET"):
                await verify_slack_signature(req)
