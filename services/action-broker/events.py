"""
Pub/Sub event publishers for the Action Broker.

Topics published (INTERFACE-CONTRACT §3):
  ops.actions.requested  — on propose_action
  ops.actions.executed   — on execute / rollback completion
  ops.audit              — on every phase transition

LIVE_MODE=False (default): log the event payload; do not call Pub/Sub.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"

TOPIC_ACTIONS_REQUESTED = "ops.actions.requested"
TOPIC_ACTIONS_EXECUTED = "ops.actions.executed"
TOPIC_AUDIT = "ops.audit"


def _publish(pubsub_client, project_id: str, topic: str, payload: Dict[str, Any]) -> None:
    import json
    data = json.dumps(payload, default=str).encode()

    if not LIVE_MODE or pubsub_client is None:
        logger.info("[DRY-RUN] Pub/Sub publish topic=%s payload=%s", topic, payload)
        return

    topic_path = pubsub_client.topic_path(project_id, topic)
    future = pubsub_client.publish(topic_path, data)
    future.result(timeout=10)
    logger.info("Published to topic=%s", topic)


def publish_action_requested(
    pubsub_client,
    project_id: str,
    action_request: Dict[str, Any],
) -> None:
    _publish(pubsub_client, project_id, TOPIC_ACTIONS_REQUESTED, action_request)


def publish_action_executed(
    pubsub_client,
    project_id: str,
    action_executed: Dict[str, Any],
) -> None:
    _publish(pubsub_client, project_id, TOPIC_ACTIONS_EXECUTED, action_executed)


def publish_audit(
    pubsub_client,
    project_id: str,
    audit_record: Dict[str, Any],
) -> None:
    _publish(pubsub_client, project_id, TOPIC_AUDIT, audit_record)
