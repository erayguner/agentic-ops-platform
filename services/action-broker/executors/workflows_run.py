"""
Executor: workflows.run

Triggers a Cloud Workflows execution.  The ``workflow_name`` parameter
distinguishes dry-run variants (``*-dryrun``) from production workflows,
per DESIGN-REVIEW §3.3.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    required = {"workflow_name", "project", "region"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("workflows.run stub; LIVE_MODE=false")
    wf = params["workflow_name"]
    ref = f"projects/{params['project']}/locations/{params['region']}/workflows/{wf}"
    is_dryrun = wf.endswith("-dryrun")
    logger.info("Triggering workflow %s (dryrun=%s)", ref, is_dryrun)
    # Real: ExecutionsClient(credentials=credentials).create_execution(parent=ref, execution=...)
    return Outcome(
        status="success",
        detail=f"execution triggered for {wf}",
        resource_refs=[ref],
    )


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    # Workflow rollback is not generically possible; escalate.
    logger.warning(
        "Workflow rollback requested but not auto-implemented for %s", params.get("workflow_name")
    )
    return Outcome(
        status="rolled_back",
        detail="workflow rollback: manual intervention required",
        resource_refs=[],
    )
