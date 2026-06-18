"""
Executor registry.

Maps canonical action_class strings to executor modules.
Each module exposes:
  validate(params)                   -> None | raises ValueError
  execute(params, credentials)       -> Outcome
  verify(params, outcome)            -> bool
  rollback(params, outcome)          -> Outcome

When LIVE_MODE=False, execute() raises NotImplementedError (stub behaviour).
The broker's flow around executors — event emission, audit, idempotency — is
always real regardless of LIVE_MODE.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType


@dataclass
class Outcome:
    """Result returned by every executor's execute()/rollback().

    Defined once here and imported by each executor (previously duplicated
    verbatim in all 10 executor modules).
    """

    status: str
    detail: str
    resource_refs: list[str]


# ---------------------------------------------------------------------------
# Canonical mapping (see ../policy/action_classes.yaml for the policy view).
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, str] = {
    "cloud_run.scale_within_range": "executors.cloud_run_scale_within_range",
    "cloud_run.restart_revision": "executors.cloud_run_restart_revision",
    "cloud_run.rollback_to_previous": "executors.cloud_run_rollback_to_previous",
    "iam.disable_service_account_key": "executors.iam_disable_service_account_key",
    "secret_manager.disable_version": "executors.secret_manager_disable_version",
    "scc.mute_finding": "executors.scc_mute_finding",
    "workflows.run": "executors.workflows_run",
    "terraform.plan": "executors.terraform_plan",
    "terraform.destroy_target": "executors.terraform_destroy_target",
    "decommission.delete_resource": "executors.decommission_delete_resource",
    "cost.shrink_idle_resource": "executors.cost_shrink_idle_resource",
    "incident.escalate_to_human": "executors.incident_escalate_to_human",
}


def get_executor(action_class: str) -> ModuleType:
    module_path = _REGISTRY.get(action_class)
    if module_path is None:
        raise KeyError(f"No executor registered for action_class={action_class!r}")
    return importlib.import_module(module_path)


def is_registered(action_class: str) -> bool:
    return action_class in _REGISTRY
