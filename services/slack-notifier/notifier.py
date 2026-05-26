"""
Notifier orchestrator: render → redact → post → ack.

Wires together blockkit.render_block_kit, redaction.redact_dict, and the
Slack WebClient to deliver an OpsNotification to the correct channel.

LIVE_SLACK_ENABLED=False (default): logs the rendered Block Kit JSON instead
of calling chat.postMessage.
"""

from __future__ import annotations

import json
import logging
import os

from blockkit import render_block_kit
from redaction import redact_dict
from schemas import OpsNotification

logger = logging.getLogger(__name__)

LIVE_SLACK_ENABLED = os.environ.get("LIVE_SLACK_ENABLED", "false").lower() == "true"


async def deliver_notification(
    notification: OpsNotification,
    slack_client,
) -> dict:
    """
    Render the notification, redact it, and post to Slack (or log in dry-run).

    Returns the Slack API response dict on success, or a synthetic dict in
    dry-run mode.
    """
    # 1. Render
    payload = render_block_kit(notification)

    # 2. Redact — belt-and-braces over Model Armor upstream screening
    payload = redact_dict(payload)

    channel: str = payload["channel"]
    text: str = payload["text"]
    blocks: list = payload["blocks"]

    logger.info(
        "Delivering notification notification_id=%s channel=%s severity=%s",
        notification.notification_id,
        channel,
        notification.severity,
    )

    if not LIVE_SLACK_ENABLED or slack_client is None:
        # Dry-run: log the full rendered payload
        logger.info(
            "[DRY-RUN] Block Kit payload (not sent to Slack):\n%s",
            json.dumps(payload, indent=2, default=str),
        )
        return {"ok": True, "dry_run": True, "channel": channel}

    # 3. Post
    try:
        resp = await slack_client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks,
        )
        logger.info("Slack postMessage ok: ts=%s channel=%s", resp.get("ts"), channel)
        return resp.data
    except Exception as exc:
        logger.exception(
            "Slack postMessage failed notification_id=%s: %s",
            notification.notification_id,
            exc,
        )
        raise
