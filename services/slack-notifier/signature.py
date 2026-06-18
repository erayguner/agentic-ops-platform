"""
Slack request signature verification.

Implements the documented Slack signing-secret protocol:
  HMAC-SHA256 over the string  "v0:<timestamp>:<raw_body>"
  Verified by comparing against the X-Slack-Signature header value.
  Timestamp window: ±5 minutes (replay-attack defence).

Reference: https://api.slack.com/authentication/verifying-requests-from-slack
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_REPLAY_WINDOW_SECONDS = 300  # 5 minutes


def _get_signing_secret() -> bytes:
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not secret:
        raise RuntimeError("SLACK_SIGNING_SECRET env var is not set")
    return secret.encode()


async def verify_slack_signature(request: Request) -> bytes:
    """
    Verify a Slack interactivity request.

    Returns the raw request body on success so the caller can decode it.
    Raises HTTP 401 / 403 on failure.
    """
    timestamp_header = request.headers.get("X-Slack-Request-Timestamp", "")
    signature_header = request.headers.get("X-Slack-Signature", "")

    if not timestamp_header or not signature_header:
        logger.warning("Slack request missing signature headers")
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    try:
        ts = int(timestamp_header)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid timestamp header") from exc

    # Replay-attack window
    now = int(time.time())
    if abs(now - ts) > _REPLAY_WINDOW_SECONDS:
        logger.warning("Slack timestamp outside replay window: ts=%s now=%s", ts, now)
        raise HTTPException(status_code=403, detail="Request timestamp too old or too new")

    body: bytes = await request.body()
    basestring = f"v0:{ts}:{body.decode()}".encode()

    expected = "v0=" + hmac.new(_get_signing_secret(), basestring, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        logger.warning("Slack signature mismatch")
        raise HTTPException(status_code=403, detail="Slack signature verification failed")

    return body
