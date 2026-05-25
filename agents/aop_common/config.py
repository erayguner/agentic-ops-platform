"""aop_common.config — Pydantic Settings for all AOP agents.

All configuration is drawn from environment variables. No value is hard-coded here.
The model id is configuration; it must never be embedded in agent code.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AopSettings(BaseSettings):
    """Platform-wide configuration loaded from environment variables.

    Env-var names follow the pattern AOP_<FIELD_UPPER>.
    All secret references point at Secret Manager paths; the actual values
    are *not* held in this object — callers retrieve them via the Secret Manager API.
    """

    model_config = SettingsConfigDict(
        env_prefix="AOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Google Cloud identity
    # ------------------------------------------------------------------ #
    project: str = Field(..., description="GCP project id for the agent runtime")
    region: str = Field("europe-west2", description="Primary GCP region")

    # ------------------------------------------------------------------ #
    # Agent identity
    # ------------------------------------------------------------------ #
    agent_identity: str = Field(
        ...,
        description=(
            "SPIFFE URI or service-account email for this agent instance. "
            "Example: spiffe://agents.example/sre  or  sa-sre@ops-agents-prod.iam.gserviceaccount.com"
        ),
    )
    environment: str = Field(
        "dev", description="Deployment environment — 'dev' or 'prod'"
    )

    # ------------------------------------------------------------------ #
    # Model configuration
    # ------------------------------------------------------------------ #
    model_id: str = Field(
        "gemini-3-pro",
        description="Primary model id passed to ADK. Never hard-coded in agent code.",
    )
    model_fallback_list: list[str] = Field(
        default_factory=lambda: ["gemini-2-flash", "gemini-2-pro"],
        description=(
            "Ordered fallback model ids. The model factory tries the primary first, "
            "then each fallback in sequence on quota/unavailability errors."
        ),
    )
    model_temperature: float = Field(0.0, ge=0.0, le=2.0)
    model_max_output_tokens: int = Field(8192, gt=0)

    # ------------------------------------------------------------------ #
    # Pub/Sub topic names  (§3 of INTERFACE-CONTRACT.md — exact names)
    # ------------------------------------------------------------------ #
    topic_signals: str = Field("ops.signals")
    topic_findings: str = Field("ops.findings")
    topic_actions_requested: str = Field("ops.actions.requested")
    topic_actions_approved: str = Field("ops.actions.approved")
    topic_actions_executed: str = Field("ops.actions.executed")
    topic_notifications: str = Field("ops.notifications")
    topic_audit: str = Field("ops.audit")

    # ------------------------------------------------------------------ #
    # Secret Manager references (paths, not values)
    # ------------------------------------------------------------------ #
    secret_slack_oauth_token: str = Field(
        "projects/{project}/secrets/slack-oauth-token/versions/latest",
        description="Secret Manager resource name for the Slack OAuth token",
    )
    secret_slack_signing_secret: str = Field(
        "projects/{project}/secrets/slack-signing-secret/versions/latest",
        description="Secret Manager resource name for the Slack signing secret",
    )

    # ------------------------------------------------------------------ #
    # Action Broker MCP endpoint
    # ------------------------------------------------------------------ #
    action_broker_mcp_endpoint: str = Field(
        ...,
        description=(
            "Streamable HTTP endpoint for the Action Broker MCP server. "
            "Example: https://action-broker-<hash>-nw.a.run.app/mcp"
        ),
    )

    # ------------------------------------------------------------------ #
    # Org Context MCP endpoint
    # ------------------------------------------------------------------ #
    org_context_mcp_endpoint: str = Field(
        ...,
        description="Streamable HTTP endpoint for the Org Context MCP server.",
    )

    # ------------------------------------------------------------------ #
    # Token / cost budgets
    # ------------------------------------------------------------------ #
    monthly_token_budget: int = Field(
        10_000_000,
        description="Hard monthly token cap per agent. A budget-burn alert fires at 80%.",
    )

    # ------------------------------------------------------------------ #
    # Firestore
    # ------------------------------------------------------------------ #
    firestore_database: str = Field(
        "(default)", description="Firestore database id for incident state"
    )

    def model_post_init(self, __context: object) -> None:
        """Expand {project} placeholder in secret paths after all fields are set."""
        self.secret_slack_oauth_token = self.secret_slack_oauth_token.format(
            project=self.project
        )
        self.secret_slack_signing_secret = self.secret_slack_signing_secret.format(
            project=self.project
        )
