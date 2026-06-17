"""
Tests for the executor registry and the shared executor contract.

Every registered action_class must resolve to a module that exposes the
four-function interface (validate / execute / verify / rollback). These tests
guard against registry drift (a class registered but unimportable, or a module
missing part of the contract) and cover the real, always-on logic in each
executor — validate() and verify() — which run regardless of LIVE_MODE.

execute() is a LIVE_MODE-gated stub for most executors (raises
NotImplementedError in dry-run); incident.escalate_to_human is the documented
exception that succeeds without touching GCP.
"""

from __future__ import annotations

import pytest
from executors import _REGISTRY as REGISTRY
from executors import Outcome, get_executor, is_registered

ALL_ACTION_CLASSES = sorted(REGISTRY)

# All executors are LIVE_MODE-gated stubs except escalate-to-human, which is
# read-only on GCP and succeeds in dry-run.
STUB_ACTION_CLASSES = [c for c in ALL_ACTION_CLASSES if c != "incident.escalate_to_human"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_is_registered_true_for_known_class(self) -> None:
        assert is_registered("cloud_run.scale_within_range")

    def test_is_registered_false_for_unknown_class(self) -> None:
        assert not is_registered("not.a.real.class")

    def test_get_executor_raises_keyerror_for_unknown_class(self) -> None:
        with pytest.raises(KeyError):
            get_executor("not.a.real.class")

    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_every_registered_class_resolves_to_a_module(self, action_class: str) -> None:
        module = get_executor(action_class)
        assert module is not None

    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_every_executor_exposes_the_contract(self, action_class: str) -> None:
        module = get_executor(action_class)
        for fn in ("validate", "execute", "verify", "rollback"):
            assert callable(getattr(module, fn, None)), f"{action_class} missing {fn}()"


# ---------------------------------------------------------------------------
# verify() — shared post-condition contract
# ---------------------------------------------------------------------------


class TestVerifyContract:
    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_verify_true_on_success_outcome(self, action_class: str) -> None:
        module = get_executor(action_class)
        outcome = Outcome(status="success", detail="ok", resource_refs=[])
        assert module.verify({}, outcome) is True

    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_verify_false_on_failed_outcome(self, action_class: str) -> None:
        module = get_executor(action_class)
        outcome = Outcome(status="failed", detail="boom", resource_refs=[])
        assert module.verify({}, outcome) is False


# ---------------------------------------------------------------------------
# execute() — dry-run gating
# ---------------------------------------------------------------------------


class TestExecuteDryRunGate:
    @pytest.mark.parametrize("action_class", STUB_ACTION_CLASSES)
    def test_stub_execute_raises_not_implemented_in_dry_run(self, action_class: str) -> None:
        module = get_executor(action_class)
        with pytest.raises(NotImplementedError):
            module.execute({}, credentials=None)

    def test_escalate_to_human_succeeds_in_dry_run(self) -> None:
        module = get_executor("incident.escalate_to_human")
        outcome = module.execute(
            {"incident_id": "inc-1", "reason": "p1", "environment": "dev"}, credentials=None
        )
        assert outcome.status == "success"


# ---------------------------------------------------------------------------
# validate() — required params (shared shape)
# ---------------------------------------------------------------------------

# (action_class, a fully-valid params dict) for every executor.
_VALID_PARAMS: dict[str, dict] = {
    "cloud_run.scale_within_range": {
        "service_name": "svc",
        "project": "p",
        "region": "us-central1",
        "instances": 3,
    },
    "cloud_run.restart_revision": {"service_name": "svc", "project": "p", "region": "r"},
    "cloud_run.rollback_to_previous": {"service_name": "svc", "project": "p", "region": "r"},
    "iam.disable_service_account_key": {
        "service_account_email": "sa@p.iam.gserviceaccount.com",
        "key_id": "k1",
        "project": "p",
    },
    "secret_manager.disable_version": {"secret_id": "s", "version": "1", "project": "p"},
    "scc.mute_finding": {"finding_name": "organizations/1/sources/2/findings/3"},
    "workflows.run": {"workflow_name": "wf", "project": "p", "region": "r"},
    "terraform.plan": {"workspace": "ws", "working_dir": "tf-workdir"},
    "terraform.destroy_target": {
        "working_dir": "tf-workdir",
        "workspace": "ws",
        "target_address": "google_storage_bucket.x",
    },
    "decommission.delete_resource": {
        "asset_type": "storage.googleapis.com/Bucket",
        "resource_name": "bkt",
        "project": "p",
    },
    "cost.shrink_idle_resource": {
        "resource_type": "instances",
        "resource_name": "vm",
        "project": "p",
        "action": "stop",
    },
    "incident.escalate_to_human": {
        "incident_id": "inc-1",
        "reason": "p1",
        "environment": "dev",
    },
}


class TestValidateRequiredParams:
    def test_every_action_class_has_valid_params_fixture(self) -> None:
        # Guards against the registry growing without a matching fixture here.
        assert set(_VALID_PARAMS) == set(ALL_ACTION_CLASSES)

    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_valid_params_pass(self, action_class: str) -> None:
        module = get_executor(action_class)
        # Should not raise.
        assert module.validate(_VALID_PARAMS[action_class]) is None

    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_empty_params_raise_value_error(self, action_class: str) -> None:
        module = get_executor(action_class)
        with pytest.raises(ValueError, match=r"(?i)missing"):
            module.validate({})

    @pytest.mark.parametrize("action_class", ALL_ACTION_CLASSES)
    def test_each_single_missing_required_param_raises(self, action_class: str) -> None:
        module = get_executor(action_class)
        valid = _VALID_PARAMS[action_class]
        for key in valid:
            partial = {k: v for k, v in valid.items() if k != key}
            with pytest.raises(ValueError, match=r"(?i)missing"):
                module.validate(partial)


# ---------------------------------------------------------------------------
# validate() — executor-specific rules
# ---------------------------------------------------------------------------


class TestValidateSpecificRules:
    def test_scale_rejects_negative_instances(self) -> None:
        module = get_executor("cloud_run.scale_within_range")
        with pytest.raises(ValueError, match="instances must be"):
            module.validate(
                {"service_name": "s", "project": "p", "region": "r", "instances": -1}
            )

    def test_scale_rejects_non_int_instances(self) -> None:
        module = get_executor("cloud_run.scale_within_range")
        with pytest.raises(ValueError, match="instances must be"):
            module.validate(
                {"service_name": "s", "project": "p", "region": "r", "instances": "three"}
            )

    def test_cost_shrink_rejects_unknown_action(self) -> None:
        module = get_executor("cost.shrink_idle_resource")
        with pytest.raises(ValueError, match="action must be one of"):
            module.validate(
                {
                    "resource_type": "instances",
                    "resource_name": "vm",
                    "project": "p",
                    "action": "nuke",
                }
            )

    @pytest.mark.parametrize("action", ["resize", "delete", "stop"])
    def test_cost_shrink_accepts_valid_actions(self, action: str) -> None:
        module = get_executor("cost.shrink_idle_resource")
        assert (
            module.validate(
                {
                    "resource_type": "instances",
                    "resource_name": "vm",
                    "project": "p",
                    "action": action,
                }
            )
            is None
        )

    def test_terraform_destroy_rejects_blank_target_address(self) -> None:
        module = get_executor("terraform.destroy_target")
        with pytest.raises(ValueError, match="target_address"):
            module.validate(
                {"working_dir": "tf-workdir", "workspace": "ws", "target_address": "   "}
            )

    def test_decommission_rejects_blank_resource_name(self) -> None:
        module = get_executor("decommission.delete_resource")
        with pytest.raises(ValueError, match="resource_name"):
            module.validate(
                {"asset_type": "Bucket", "resource_name": "  ", "project": "p"}
            )
