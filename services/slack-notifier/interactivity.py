"""
Slack interactivity handler.

Receives ``block_actions`` payloads from the Slack Interactivity endpoint,
resolves the acting Slack user to an operator email, and publishes an
``ActionApproval v1`` event to the ``ops.actions.approved`` Pub/Sub topic.

LIVE_SLACK_ENABLED=False (default): logs the approval payload instead of
  publishing to Pub/Sub.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import uuid
from datetime import datetime, timezone

from schemas import ActionApproval

logger = logging.getLogger(__name__)

LIVE_SLACK_ENABLED = os.environ.get("LIVE_SLACK_ENABLED", "false").lower() == "true"
TOPIC_ACTIONS_APPROVED = "ops.actions.approved"


# ---------------------------------------------------------------------------
# User resolution  (Slack user ID → operator email)
# ---------------------------------------------------------------------------

async def _resolve_operator_email(slack_user_id: str, slack_client) -> str:
    """
    Look up the Slack user's email via the ``users.info`` API.
    Falls back to returning the raw user ID on any error.
    """
    if not LIVE_SLACK_ENABLED or slack_client is None:
        return f"slack:{slack_user_id}@local"
    try:
        resp = await slack_client.users_info(user=slack_user_id)
        profile = resp.get("user", {}).get("profile", {})
        return profile.get("email") or f"slack:{slack_user_id}"
    except Exception as exc:
        logger.warning("Could not resolve Slack user %s: %s", slack_user_id, exc)
        return f"slack:{slack_user_id}"


# ---------------------------------------------------------------------------
# Approval publisher
# ---------------------------------------------------------------------------

async def _publish_approval(approval: ActionApproval, pubsub_client) -> None:
    """Publish ActionApproval to ops.actions.approved."""
    topic_path = pubsub_client.topic_path(
        os.environ.get("GCP_PROJECT_ID", "ops-agents-dev"),
        TOPIC_ACTIONS_APPROVED,
    )
    data = approval.model_dump_json(by_alias=True).encode()
    future = pubsub_client.publish(topic_path, data)
    future.result(timeout=10)
    logger.info("Published ActionApproval action_id=%s decision=%s", approval.action_id, approval.decision)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def handle_block_actions(
    raw_payload: str,
    slack_client,
    pubsub_client,
) -> dict:
    """
    Parse a Slack ``block_actions`` payload and emit an ``ActionApproval``.

    Returns a dict suitable for returning as the HTTP response body
    (Slack ignores the body of interactivity acks but we log it).
    """
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        logger.error("Malformed interactivity payload: %s", exc)
        return {"ok": False, "error": "invalid_payload"}

    if payload.get("type") != "block_actions":
        logger.debug("Unhandled interactivity type: %s", payload.get("type"))
        return {"ok": True, "ignored": True}

    actions: list[dict] = payload.get("actions", [])
    if not actions:
        return {"ok": True, "ignored": True}

    action = actions[0]
    action_id_raw: str = action.get("action_id", "")
    action_value: str = action.get("value", "")

    # Determine decision from action_id prefix
    if action_id_raw.startswith("approve_"):
        decision = "approved"
    elif action_id_raw.startswith("reject_"):
        decision = "rejected"
    else:
        logger.debug("Unhandled action_id prefix: %s", action_id_raw)
        return {"ok": True, "ignored": True}

    slack_user = payload.get("user", {}).get("id", "unknown")
    operator_email = await _resolve_operator_email(slack_user, slack_client)

    approval = ActionApproval(
        action_id=action_value,
        approval_id=f"apv_{uuid.uuid4().hex[:12]}",
        decision=decision,
        approver_identity=[operator_email],
        approved_at=datetime.now(tz=timezone.utc),
    )

    if LIVE_SLACK_ENABLED and pubsub_client is not None:
        await _publish_approval(approval, pubsub_client)
    else:
        logger.info(
            "[DRY-RUN] ActionApproval (not published): %s",
            approval.model_dump_json(indent=2),
        )

    return {"ok": True, "decision": decision, "action_id": action_value}
