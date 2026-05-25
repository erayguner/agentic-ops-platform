"""Executor: secret_manager.disable_version — stub."""
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
    required = {"secret_id", "version", "project"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: Dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("secret_manager.disable_version stub; LIVE_MODE=false")
    ref = f"projects/{params['project']}/secrets/{params['secret_id']}/versions/{params['version']}"
    logger.info("Disabling secret version %s", ref)
    # Real: SecretManagerServiceClient(credentials=credentials).disable_secret_version(name=ref)
    return Outcome(status="success", detail=f"version {params['version']} disabled", resource_refs=[ref])


def verify(params: Dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: Dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    logger.info("Re-enabling secret version %s", params.get("version"))
    return Outcome(status="rolled_back", detail="version re-enabled", resource_refs=[])
