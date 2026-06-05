"""Executor: terraform.plan — stub (read-only; no apply)."""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    required = {"workspace", "working_dir"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("terraform.plan stub; LIVE_MODE=false")
    wd = params["working_dir"]
    logger.info("Running terraform plan in %s (workspace=%s)", wd, params["workspace"])
    # Real: subprocess.run(["terraform", "plan", "-out=plan.json"], cwd=wd, ...)
    return Outcome(status="success", detail="terraform plan completed", resource_refs=[wd])


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    # plan is read-only; rollback is a no-op
    return Outcome(
        status="rolled_back",
        detail="terraform plan is read-only; no rollback needed",
        resource_refs=[],
    )
