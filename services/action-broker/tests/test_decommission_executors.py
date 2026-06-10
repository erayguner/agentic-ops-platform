"""
Tests for the decommission teardown path in the Action Broker:
- terraform_destroy_target / decommission_delete_resource executors
- registry registration
- policy entries (tiers, approver counts, max_blast_radius bounds)
"""

import pytest
from executors import Outcome, get_executor, is_registered
from executors import decommission_delete_resource as ddr
from executors import terraform_destroy_target as tdt
from policy import PolicyEngine

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_both_executors_registered(self) -> None:
        assert is_registered("terraform.destroy_target")
        assert is_registered("decommission.delete_resource")

    def test_get_executor_resolves(self) -> None:
        assert get_executor("terraform.destroy_target") is tdt
        assert get_executor("decommission.delete_resource") is ddr


# ---------------------------------------------------------------------------
# terraform.destroy_target
# ---------------------------------------------------------------------------


class TestTerraformDestroyTarget:
    def test_validate_requires_params(self) -> None:
        with pytest.raises(ValueError, match="Missing params"):
            tdt.validate({"working_dir": "x"})

    def test_validate_rejects_empty_address(self) -> None:
        with pytest.raises(ValueError, match="target_address"):
            tdt.validate({"working_dir": "x", "workspace": "dev", "target_address": "  "})

    def test_validate_accepts_complete_params(self) -> None:
        tdt.validate({"working_dir": "x", "workspace": "dev", "target_address": "module.a.b"})

    def test_execute_is_stub_without_live_mode(self) -> None:
        with pytest.raises(NotImplementedError):
            tdt.execute(
                {"working_dir": "x", "workspace": "dev", "target_address": "module.a.b"}, None
            )

    def test_rollback_reports_irreversible(self) -> None:
        outcome = tdt.rollback(
            {"target_address": "module.a.b"}, Outcome(status="success", detail="", resource_refs=[])
        )
        assert outcome.status == "failed"
        assert "irreversible" in outcome.detail


# ---------------------------------------------------------------------------
# decommission.delete_resource
# ---------------------------------------------------------------------------


class TestDecommissionDeleteResource:
    def test_validate_requires_params(self) -> None:
        with pytest.raises(ValueError, match="Missing params"):
            ddr.validate({"asset_type": "x"})

    def test_execute_is_stub_without_live_mode(self) -> None:
        with pytest.raises(NotImplementedError):
            ddr.execute({"asset_type": "t", "resource_name": "n", "project": "p"}, None)

    def test_rollback_reports_irreversible(self) -> None:
        outcome = ddr.rollback(
            {"resource_id": "//x/y"}, Outcome(status="success", detail="", resource_refs=[])
        )
        assert outcome.status == "failed"
        assert "irreversible" in outcome.detail


# ---------------------------------------------------------------------------
# Policy — destroys are human-approved and blast-radius bounded
# ---------------------------------------------------------------------------


class TestDecommissionPolicy:
    def test_terraform_destroy_dev_is_single_approver_tier3(self) -> None:
        decision = PolicyEngine.load().decide(
            "terraform.destroy_target", "dev", {}, {"target_count": 5}
        )
        assert decision.allowed is True
        assert decision.tier == 3
        assert decision.required_approvers == 1

    def test_terraform_destroy_prod_requires_two_approvers(self) -> None:
        decision = PolicyEngine.load().decide(
            "terraform.destroy_target", "prod", {}, {"target_count": 5}
        )
        assert decision.allowed is True
        assert decision.tier == 3
        assert decision.required_approvers == 2

    def test_terraform_destroy_prod_blast_radius_enforced(self) -> None:
        decision = PolicyEngine.load().decide(
            "terraform.destroy_target", "prod", {}, {"target_count": 11}
        )
        assert decision.allowed is False
        assert "bounds_violation" in (decision.deny_reason or "")

    def test_delete_resource_prod_blast_radius_tighter(self) -> None:
        engine = PolicyEngine.load()
        assert engine.decide(
            "decommission.delete_resource", "prod", {}, {"target_count": 5}
        ).allowed
        denied = engine.decide("decommission.delete_resource", "prod", {}, {"target_count": 6})
        assert denied.allowed is False

    def test_unknown_environment_defaults_deny(self) -> None:
        decision = PolicyEngine.load().decide(
            "terraform.destroy_target", "staging", {}, {"target_count": 1}
        )
        assert decision.allowed is False
