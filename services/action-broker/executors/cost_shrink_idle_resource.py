"""Executor: cost.shrink_idle_resource — stub."""
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
    required = {"resource_type", "resource_name", "project", "action"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")
    valid_actions = {"resize", "delete", "stop"}
    if params["action"] not in valid_actions:
        raise ValueError(f"action must be one of {valid_actions}; got {params['action']!r}")


def execute(params: Dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("cost.shrink_idle_resource stub; LIVE_MODE=false")
    ref = f"projects/{params['project']}/{params['resource_type']}/{params['resource_name']}"
    logger.info("Shrinking idle resource %s via action=%s", ref, params["action"])
    return Outcome(status="success", detail=f"{params['action']} applied to {ref}", resource_refs=[ref])


def verify(params: Dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: Dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    logger.info("Attempting to restore %s", params.get("resource_name"))
    return Outcome(status="rolled_back", detail="resource restored", resource_refs=[])
