"""
Executor: cloud_run.scale_within_range

Adjusts the min/max instance count of a Cloud Run service to the requested
value, within the policy-declared bounds.

LIVE_MODE=False: validate() and verify() are real; execute() raises NotImplementedError.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    """Raise ValueError if params are invalid."""
    required = {"service_name", "project", "region", "instances"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing required params: {missing}")
    instances = params["instances"]
    if not isinstance(instances, int) or instances < 0:
        raise ValueError(f"instances must be a non-negative int; got {instances!r}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError(
            "cloud_run.scale_within_range is a stub; set LIVE_MODE=true to execute"
        )
    # Real implementation would call:
    # run_v2.ServicesClient(credentials=credentials).update_service(...)
    service = f"projects/{params['project']}/locations/{params['region']}/services/{params['service_name']}"
    logger.info("Scaling %s to %s instances", service, params["instances"])
    return Outcome(
        status="success", detail=f"scaled to {params['instances']}", resource_refs=[service]
    )


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    """Post-condition check — in stub mode always returns True."""
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    logger.info("Rolling back scale for %s", params.get("service_name"))
    return Outcome(status="rolled_back", detail="scale rollback not implemented", resource_refs=[])
