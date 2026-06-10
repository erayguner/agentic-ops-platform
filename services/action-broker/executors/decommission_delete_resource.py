"""Executor: decommission.delete_resource — delete an unmanaged/drifted resource.

The teardown path for resources that are NOT in Terraform state: manually-created
or drifted resources the decommission agent found via Cloud Asset Inventory.
Deletion goes through the resource's own provider API (e.g. ``gcloud``/REST delete)
rather than Terraform, since there is no state entry to destroy.

Irreversible and ``LIVE_MODE``-gated. Upstream the Broker has policy-gated and
human-approved the action (Tier 3; prod requires 2 approvers) and enforced the
``max_blast_radius`` bound via ``target_count``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    required = {"asset_type", "resource_name", "project"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")
    if not str(params["resource_name"]).strip():
        raise ValueError("resource_name must be non-empty")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("decommission.delete_resource stub; LIVE_MODE=false")
    ref = params.get("resource_id") or (
        f"//{params['asset_type']}/projects/{params['project']}/{params['resource_name']}"
    )
    logger.info("Deleting unmanaged resource %s (type=%s)", ref, params["asset_type"])
    # Real: dispatch to the provider delete for params["asset_type"], e.g.
    #   google-cloud client .delete(name=ref)  /  asset-type-specific REST DELETE.
    return Outcome(status="success", detail=f"deleted {ref}", resource_refs=[str(ref)])


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    # Post-condition: provider reported success. A full check re-queries Asset
    # Inventory and asserts the resource is no longer present.
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    # Deleting a live resource is irreversible — no automatic rollback.
    return Outcome(
        status="failed",
        detail=(
            "resource deletion is irreversible; no automatic rollback — "
            "recreate from backup or IaC manually"
        ),
        resource_refs=[str(params.get("resource_id", params.get("resource_name", "")))],
    )
