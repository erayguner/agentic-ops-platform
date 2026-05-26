"""Executor: cloud_run.restart_revision — stub."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


@dataclass
class Outcome:
    status: str
    detail: str
    resource_refs: list[str]


def validate(params: dict[str, Any]) -> None:
    required = {"service_name", "project", "region"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("cloud_run.restart_revision stub; LIVE_MODE=false")
    service = f"projects/{params['project']}/locations/{params['region']}/services/{params['service_name']}"
    logger.info("Restarting %s", service)
    return Outcome(status="success", detail="revision restarted", resource_refs=[service])


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    return Outcome(status="rolled_back", detail="restart rollback n/a", resource_refs=[])
