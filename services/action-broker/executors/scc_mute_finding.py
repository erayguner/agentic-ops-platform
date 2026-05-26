"""Executor: scc.mute_finding — stub."""

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
    required = {"finding_name"}  # full resource name e.g. organizations/.../findings/...
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("scc.mute_finding stub; LIVE_MODE=false")
    finding = params["finding_name"]
    logger.info("Muting SCC finding %s", finding)
    # Real: SecurityCenterClient(credentials=credentials).set_mute(request={"name": finding, "mute": "MUTED"})
    return Outcome(status="success", detail="finding muted", resource_refs=[finding])


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    logger.info("Unmuting finding %s", params.get("finding_name"))
    return Outcome(status="rolled_back", detail="finding unmuted", resource_refs=[])
