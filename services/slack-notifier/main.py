"""
Slack-notifier Cloud Run service.

Endpoints:
  POST /pubsub/push      — Pub/Sub push subscription (ops.notifications)
  POST /slack/interactivity — Slack interactivity (block_actions)
  GET  /healthz          — liveness probe

Environment variables:
  LIVE_SLACK_ENABLED      (default: false) — when false, log instead of calling Slack
  SLACK_BOT_TOKEN         — xoxb-... OAuth token (from Secret Manager at runtime)
  SLACK_SIGNING_SECRET    — for request signature verification
  PUBSUB_PUSH_TOKEN       — shared secret embedded in the push subscription URL
  GCP_PROJECT_ID          — target GCP project for Pub/Sub publishing
"""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from pydantic import ValidationError

from interactivity import handle_block_actions
from notifier import deliver_notification
from schemas import OpsNotification
from signature import verify_slack_signature

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

LIVE_SLACK_ENABLED = os.environ.get("LIVE_SLACK_ENABLED", "false").lower() == "true"
PUBSUB_PUSH_TOKEN = os.environ.get("PUBSUB_PUSH_TOKEN", "")


# ---------------------------------------------------------------------------
# Lifespan — client initialisation
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise Slack and Pub/Sub clients once at startup."""
    slack_client = None
    pubsub_client = None

    if LIVE_SLACK_ENABLED:
        from slack_sdk.web.async_client import AsyncWebClient  # type: ignore
        from google.cloud import pubsub_v1

        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            logger.warning("LIVE_SLACK_ENABLED=true but SLACK_BOT_TOKEN is empty")
        slack_client = AsyncWebClient(token=token)
        pubsub_client = pubsub_v1.PublisherClient()
        logger.info("Live Slack client and Pub/Sub publisher initialised")
    else:
        logger.info("LIVE_SLACK_ENABLED=false — dry-run mode; no Slack/Pub/Sub clients")

    _state["slack"] = slack_client
    _state["pubsub"] = pubsub_client
    yield
    _state.clear()


app = FastAPI(title="aop-slack-notifier", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/healthz", status_code=200)
async def healthz() -> dict:
    return {"status": "ok", "live_slack": LIVE_SLACK_ENABLED}


# ---------------------------------------------------------------------------
# Pub/Sub push handler
# ---------------------------------------------------------------------------

@app.post("/pubsub/push", status_code=204)
async def pubsub_push(
    request: Request,
    token: str = Query(default=""),
) -> Response:
    """
    Receive a Pub/Sub push message containing an OpsNotification v1 payload.

    The push subscription is configured with ?token=<PUBSUB_PUSH_TOKEN> in the
    endpoint URL; we verify the token to prevent unauthenticated calls.
    """
    if PUBSUB_PUSH_TOKEN and token != PUBSUB_PUSH_TOKEN:
        logger.warning("Pub/Sub push: invalid token")
        raise HTTPException(status_code=401, detail="Invalid push token")

    body = await request.json()
    message = body.get("message", {})
    data_b64: str = message.get("data", "")

    try:
        raw_data = base64.b64decode(data_b64).decode()
        payload = json.loads(raw_data)
    except Exception as exc:
        logger.error("Failed to decode Pub/Sub message: %s", exc)
        # Return 204 to ack (avoid infinite DLQ loop on permanently bad message)
        return Response(status_code=204)

    try:
        notification = OpsNotification(**payload)
    except ValidationError as exc:
        logger.error("OpsNotification validation failed: %s", exc)
        return Response(status_code=204)

    try:
        await deliver_notification(notification, _state.get("slack"))
    except Exception as exc:
        logger.error("deliver_notification failed: %s", exc, exc_info=True)
        # Return 500 so Pub/Sub retries (transient Slack error)
        raise HTTPException(status_code=500, detail="Delivery failed; will retry")

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Slack interactivity
# ---------------------------------------------------------------------------

@app.post("/slack/interactivity")
async def slack_interactivity(request: Request) -> dict:
    """
    Handle Slack block_actions (Approve / Reject buttons).

    Verifies the Slack signing secret, parses the form-encoded payload, and
    delegates to handle_block_actions which publishes ActionApproval.
    """
    raw_body = await verify_slack_signature(request)

    # Slack sends interactivity as form-encoded: payload=<url-encoded JSON>
    try:
        form = urllib.parse.parse_qs(raw_body.decode())
        raw_payload = form.get("payload", ["{}"])[0]
    except Exception as exc:
        logger.error("Could not parse interactivity form body: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid interactivity body")

    result = await handle_block_actions(
        raw_payload=raw_payload,
        slack_client=_state.get("slack"),
        pubsub_client=_state.get("pubsub"),
    )
    return result
