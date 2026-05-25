"""
Short-lived token minting via IAM Credentials API.

The Action Broker (running as ``sa-action-broker``) uses
``iam.serviceAccountTokenCreator`` on each per-action-class SA to generate a
short-lived access token (≤1 h).  The token is wrapped in a
``google.oauth2.credentials.Credentials`` object so Google Cloud client
libraries consume it transparently.

LIVE_MODE=False: returns a stub Credentials object; no real IAM call is made.

SA naming convention (INTERFACE-CONTRACT §2):
  sa-action-<class-slug>@<project>.iam.gserviceaccount.com

Example:
  cloud_run.scale_within_range → sa-action-cloudrun-scale
  iam.disable_service_account_key → sa-action-iam-disable-key
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "ops-agents-dev")

# Map action_class → per-action-class SA slug (INTERFACE-CONTRACT §2)
_ACTION_SA_MAP: dict[str, str] = {
    "cloud_run.scale_within_range":       "sa-action-cloudrun-scale",
    "cloud_run.restart_revision":         "sa-action-cloudrun-rollback",
    "cloud_run.rollback_to_previous":     "sa-action-cloudrun-rollback",
    "iam.disable_service_account_key":    "sa-action-iam-disable-key",
    "secret_manager.disable_version":     "sa-action-secret-disable",
    "scc.mute_finding":                   "sa-action-scc-mute",
    "workflows.run":                      "sa-action-workflows-run",
    "terraform.plan":                     "sa-action-terraform-plan",
    "cost.shrink_idle_resource":          "sa-action-cloudrun-scale",  # reuse scoped SA
    "incident.escalate_to_human":         "sa-action-cloudrun-scale",  # read-only; SA unused
}

_TOKEN_LIFETIME_SECONDS = 3600  # 1 hour maximum


def sa_email_for_action(action_class: str, project_id: str) -> Optional[str]:
    slug = _ACTION_SA_MAP.get(action_class)
    if slug is None:
        return None
    return f"{slug}@{project_id}.iam.gserviceaccount.com"


def mint_credentials(action_class: str, project_id: str = GCP_PROJECT_ID):
    """
    Return ``google.oauth2.credentials.Credentials`` backed by a short-lived
    access token for the per-action-class service account.

    In dry-run mode returns a stub object that cannot be used for real API
    calls but satisfies type checks.
    """
    sa_email = sa_email_for_action(action_class, project_id)
    if sa_email is None:
        raise ValueError(f"No per-action-class SA mapped for action_class={action_class!r}")

    if not LIVE_MODE:
        logger.info(
            "[DRY-RUN] Would mint credentials for SA=%s action_class=%s",
            sa_email, action_class,
        )
        return _StubCredentials(sa_email)

    from google.cloud import iam_credentials_v1  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore

    client = iam_credentials_v1.IAMCredentialsClient()
    name = f"projects/-/serviceAccounts/{sa_email}"

    resp = client.generate_access_token(
        request={
            "name": name,
            "scope": ["https://www.googleapis.com/auth/cloud-platform"],
            "lifetime": {"seconds": _TOKEN_LIFETIME_SECONDS},
        }
    )

    expiry = datetime.now(tz=timezone.utc) + timedelta(seconds=_TOKEN_LIFETIME_SECONDS)
    logger.info("Minted short-lived token for SA=%s", sa_email)
    return Credentials(token=resp.access_token, expiry=expiry)


class _StubCredentials:
    """Minimal stub used in dry-run mode."""
    def __init__(self, sa_email: str) -> None:
        self.token = "DRY_RUN_TOKEN"
        self.sa_email = sa_email
        self.expiry = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        self.valid = False

    def refresh(self, request):  # noqa: D401
        raise NotImplementedError("Stub credentials cannot be refreshed")
