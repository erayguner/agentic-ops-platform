"""
Tests for impersonation.py — sa_email_for_action and mint_credentials.

Coverage gaps addressed:
- sa_email_for_action: all mapped action classes, unknown class
- mint_credentials: dry-run returns _StubCredentials, unknown class raises ValueError
- _StubCredentials: attributes, refresh raises NotImplementedError
- SA email format: project ID interpolation
"""

from datetime import UTC
from unittest.mock import patch

import pytest
from impersonation import _StubCredentials, mint_credentials, sa_email_for_action

# ---------------------------------------------------------------------------
# sa_email_for_action
# ---------------------------------------------------------------------------


class TestSaEmailForAction:
    def test_known_action_class_returns_formatted_email(self) -> None:
        email = sa_email_for_action("cloud_run.scale_within_range", "my-project")
        assert email == "sa-action-cloudrun-scale@my-project.iam.gserviceaccount.com"

    def test_iam_action_returns_correct_sa(self) -> None:
        email = sa_email_for_action("iam.disable_service_account_key", "proj")
        assert email == "sa-action-iam-disable-key@proj.iam.gserviceaccount.com"

    def test_terraform_plan_maps_to_correct_sa(self) -> None:
        email = sa_email_for_action("terraform.plan", "proj")
        assert email == "sa-action-terraform-plan@proj.iam.gserviceaccount.com"

    def test_unknown_action_class_returns_none(self) -> None:
        assert sa_email_for_action("unknown.action", "proj") is None

    def test_project_id_is_interpolated_into_email(self) -> None:
        email = sa_email_for_action("workflows.run", "custom-project-123")
        assert "custom-project-123" in email
        assert email.endswith(".iam.gserviceaccount.com")

    def test_all_mapped_action_classes_return_non_none(self) -> None:
        action_classes = [
            "cloud_run.scale_within_range",
            "cloud_run.restart_revision",
            "cloud_run.rollback_to_previous",
            "iam.disable_service_account_key",
            "secret_manager.disable_version",
            "scc.mute_finding",
            "workflows.run",
            "terraform.plan",
            "cost.shrink_idle_resource",
            "incident.escalate_to_human",
        ]
        for cls in action_classes:
            assert sa_email_for_action(cls, "proj") is not None, f"Missing mapping: {cls}"


# ---------------------------------------------------------------------------
# mint_credentials — dry-run
# ---------------------------------------------------------------------------


class TestMintCredentialsDryRun:
    def test_dry_run_returns_stub_credentials(self) -> None:
        with patch("impersonation.LIVE_MODE", False):
            creds = mint_credentials("cloud_run.scale_within_range", "proj")
        assert isinstance(creds, _StubCredentials)

    def test_stub_token_is_dry_run_sentinel(self) -> None:
        with patch("impersonation.LIVE_MODE", False):
            creds = mint_credentials("cloud_run.scale_within_range", "proj")
        assert creds.token == "DRY_RUN_TOKEN"

    def test_stub_valid_is_false(self) -> None:
        with patch("impersonation.LIVE_MODE", False):
            creds = mint_credentials("cloud_run.scale_within_range", "proj")
        assert creds.valid is False

    def test_stub_sa_email_matches_expected_sa(self) -> None:
        with patch("impersonation.LIVE_MODE", False):
            creds = mint_credentials("cloud_run.scale_within_range", "my-proj")
        assert "sa-action-cloudrun-scale" in creds.sa_email
        assert "my-proj" in creds.sa_email

    def test_unknown_action_class_raises_value_error(self) -> None:
        with (
            patch("impersonation.LIVE_MODE", False),
            pytest.raises(ValueError, match="No per-action-class SA mapped"),
        ):
            mint_credentials("not.a.real.action", "proj")


# ---------------------------------------------------------------------------
# _StubCredentials
# ---------------------------------------------------------------------------


class TestStubCredentials:
    def test_refresh_raises_not_implemented_error(self) -> None:
        stub = _StubCredentials("sa@proj.iam.gserviceaccount.com")
        with pytest.raises(NotImplementedError):
            stub.refresh(None)

    def test_expiry_is_in_the_future(self) -> None:
        from datetime import datetime

        stub = _StubCredentials("sa@proj.iam.gserviceaccount.com")
        assert stub.expiry > datetime.now(tz=UTC)
