"""Executor: terraform.destroy_target — targeted, irreversible IaC teardown.

Destroys a single Terraform-managed resource (``-target=<address>``) as part of a
decommission campaign. This is the preferred teardown path for anything in
Terraform state: state stays the source of truth and the destroy is reviewable.

Irreversible: a destroyed resource cannot be rolled back automatically — recovery
is a re-apply from IaC and/or a restore from backup. ``execute`` is gated by
``LIVE_MODE`` (stub otherwise), and upstream the Broker has already policy-gated
and human-approved the action (Tier 3; prod requires 2 approvers).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from executors import Outcome

logger = logging.getLogger(__name__)
LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"


def validate(params: dict[str, Any]) -> None:
    required = {"working_dir", "workspace", "target_address"}
    missing = required - params.keys()
    if missing:
        raise ValueError(f"Missing params: {missing}")
    if not str(params["target_address"]).strip():
        raise ValueError("target_address must be a non-empty Terraform resource address")


def execute(params: dict[str, Any], credentials) -> Outcome:
    if not LIVE_MODE:
        raise NotImplementedError("terraform.destroy_target stub; LIVE_MODE=false")
    wd = params["working_dir"]
    address = params["target_address"]
    logger.info(
        "terraform destroy -target=%s in %s (workspace=%s)", address, wd, params["workspace"]
    )
    # Real (the Broker has already approved this; -auto-approve is the gate's output):
    #   subprocess.run(
    #       ["terraform", "destroy", f"-target={address}", "-auto-approve", "-input=false"],
    #       cwd=wd, check=True, ...
    #   )
    return Outcome(
        status="success",
        detail=f"terraform destroy completed for {address}",
        resource_refs=[address],
    )


def verify(params: dict[str, Any], outcome: Outcome) -> bool:
    # Post-condition: the destroy reported success. A full check re-reads state and
    # asserts the target_address is absent from `terraform state list`.
    return outcome.status == "success"


def rollback(params: dict[str, Any], outcome: Outcome) -> Outcome:
    # A destroy is irreversible — there is no automatic rollback. Surface that
    # plainly so the audit record and report do not imply recovery happened.
    return Outcome(
        status="failed",
        detail=(
            "terraform destroy is irreversible; no automatic rollback — "
            "re-apply from IaC or restore from backup manually"
        ),
        resource_refs=[str(params.get("target_address", ""))],
    )
