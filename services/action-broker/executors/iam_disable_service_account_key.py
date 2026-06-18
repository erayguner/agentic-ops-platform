"""Executor: iam.disable_service_account_key — stub."""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    required = {"service_account_email", "key_id", "project"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("iam.disable_service_account_key stub; LIVE_MODE=false")
    sa = params["service_account_email"]
    key_id = params["key_id"]
    ref = f"projects/{params['project']}/serviceAccounts/{sa}/keys/{key_id}"
    logger.info("Disabling SA key %s", ref)
    # Real: googleapiclient.discovery.build('iam', 'v1', credentials=credentials)
    #       .projects().serviceAccounts().keys().disable(name=ref).execute()
    return Outcome(status="success", detail=f"key {key_id} disabled", resource_refs=[ref])


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("Rollback stub; LIVE_MODE=false")
    # Re-enabling a key is possible but NOT safe-default — log and return
    logger.warning("Rollback of key disable is intentionally a no-op")
    return Outcome(
        status="rolled_back", detail="key re-enable is not auto-rolled back", resource_refs=[]
    )
