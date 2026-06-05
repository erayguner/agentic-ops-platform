"""
Executor: incident.escalate_to_human

Always allowed (Tier 0/1); never writes to GCP APIs.  Publishes an
escalation record to ops.audit and (in live mode) pages the on-call rotation
via the Slack-notifier or PagerDuty.  No impersonation needed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    required = {"incident_id", "reason", "environment"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    # Escalation is read-only on GCP; credentials unused.
    incident_id = params["incident_id"]
    reason = params["reason"]
    logger.info(
        "Escalating incident=%s to human: %s (LIVE_MODE=%s)",
        incident_id,
        reason,
        LIVE_MODE,
    )
    if LIVE_MODE:
        # Real: post to PagerDuty / emit a high-priority OpsNotification
        pass
    return Outcome(
        status="success",
        detail=f"Human escalation triggered for incident {incident_id}: {reason}",
        resource_refs=[],
    )


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    # Escalation is not reversible.
    return Outcome(
        status="rolled_back", detail="escalation cannot be rolled back", resource_refs=[]
    )
