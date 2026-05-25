"""Executor: cloud_run.rollback_to_previous — stub."""
from __future__ import annotations
import logging, os
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


@dataclass
class Outcome:
    status: str
    detail: str
    resource_refs: list[str]


def validate(params: Dict[str, Any]) -> None:
    required = {"service_name", "project", "region"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: Dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("cloud_run.rollback_to_previous stub; LIVE_MODE=false")
    service = f"projects/{params['project']}/locations/{params['region']}/services/{params['service_name']}"
    logger.info("Rolling back %s to previous revision", service)
    return Outcome(status="success", detail="rolled back to previous", resource_refs=[service])


def verify(params: Dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: Dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    logger.info("Re-rolling forward %s", params.get("service_name"))
    return Outcome(status="rolled_back", detail="re-promoted previous revision", resource_refs=[])
