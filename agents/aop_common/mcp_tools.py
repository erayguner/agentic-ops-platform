"""aop_common.mcp_tools — ADK 2.0 McpToolset wiring for managed Google MCP servers.

All MCP endpoints follow the managed fleet pattern:
    https://<service>.googleapis.com/mcp

Authentication is Application Default Credentials (ADC); no exported keys.
Each agent passes its allow-list of endpoint strings; this module builds
the McpToolset filtered to only those endpoints.

ADK 2.0 API — confirm signature against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Managed MCP endpoint constants (DESIGN-REVIEW §2.7).
# --------------------------------------------------------------------------- #

LOGGING_MCP = "https://logging.googleapis.com/mcp"
MONITORING_MCP = "https://monitoring.googleapis.com/mcp"
TRACE_MCP = "https://cloudtrace.googleapis.com/mcp"
ERROR_REPORTING_MCP = "https://clouderrorreporting.googleapis.com/mcp"
GKE_MCP = "https://container.googleapis.com/mcp"
CLOUD_RUN_MCP = "https://run.googleapis.com/mcp"
COMPUTE_MCP = "https://compute.googleapis.com/mcp"
RESOURCE_MANAGER_MCP = "https://cloudresourcemanager.googleapis.com/mcp"
ASSET_INVENTORY_MCP = "https://cloudasset.googleapis.com/mcp"  # Preview
SECOPS_MCP_TEMPLATE = "https://chronicle.{region}.rep.googleapis.com/mcp"  # GA
PUBSUB_MCP = "https://pubsub.googleapis.com/mcp"
BIGQUERY_MCP = "https://bigquery.googleapis.com/mcp"
NETWORK_INTELLIGENCE_MCP = "https://networkmanagement.googleapis.com/mcp"
AGENT_REGISTRY_MCP = "https://agentregistry.googleapis.com/mcp"  # Preview
GEMINI_CLOUD_ASSIST_MCP = "https://geminicloudassist.googleapis.com/mcp"  # Preview
RECOMMENDER_MCP = "https://recommender.googleapis.com/mcp"
DEVELOPER_KNOWLEDGE_MCP = (
    "https://developerknowledge.googleapis.com/mcp"  # GA — Google developer documentation lookup
)

# Per-agent allow-lists — curated to the purpose-fit, READ-ONLY set for the AOP
# architecture (Cloud Run + Pub/Sub + BigQuery + observability; no GKE/Compute).
# Policy (full rationale in docs/deployment/MCP-SERVERS.md):
#   * Read-only only. Each agent SA holds viewer roles + roles/mcp.toolUser;
#     every mutation/remediation goes through the Action Broker (decision/
#     execution separation) — never a direct MCP write.
#   * Excluded: GKE/Compute (not in the stack), Resource Manager (overlaps Asset
#     Inventory), SecOps/Chronicle (not used here), and Preview/unverified
#     servers (Gemini Cloud Assist, Developer Knowledge, Agent Registry,
#     Recommender) to avoid broad/ambiguous surface.
#   * Deferred: BigQuery + Pub/Sub MCP. FinOps billing-BigQuery (read-only) is
#     the first planned addition — see MCP-SERVERS.md.
ORCHESTRATOR_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    MONITORING_MCP,
]

SRE_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    MONITORING_MCP,
    TRACE_MCP,
    ERROR_REPORTING_MCP,
    CLOUD_RUN_MCP,
    NETWORK_INTELLIGENCE_MCP,
]

DEVSECOPS_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    MONITORING_MCP,
    ASSET_INVENTORY_MCP,
]

PLATFORM_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    MONITORING_MCP,
    ASSET_INVENTORY_MCP,
    CLOUD_RUN_MCP,
]

FINOPS_MCP_ENDPOINTS: list[str] = [
    MONITORING_MCP,
]

# Decommission is a read-only *discovery* surface: it inventories the estate
# (Cloud Asset Inventory) and reads activity signals (Monitoring, Logging) to
# classify dormant/idle/orphaned/billable resources, then proposes every
# teardown through the Action Broker. It holds NO delete/write IAM —
# irreversible destroys go via the Broker's policy-gated
# `terraform.destroy_target` / `decommission.delete_resource` executors only.
# Resource Manager MCP stays excluded per the fleet policy above (overlaps
# Asset Inventory); project metadata reads are bounded by the SA's
# resourcemanager.projectViewer role. Recommender MCP is deferred (Preview),
# matching FinOps — the recommender.viewer role is granted for when it lands.
DECOMMISSION_MCP_ENDPOINTS: list[str] = [
    ASSET_INVENTORY_MCP,
    MONITORING_MCP,
    LOGGING_MCP,
]


def build_mcp_toolsets(
    allowed_endpoints: list[str],
    *,
    region: str = "europe-west2",
    extra_custom_endpoints: list[str] | None = None,
) -> list[Any]:
    """Return a list of ADK 2.0 McpToolset instances, one per allowed endpoint.

    Args:
        allowed_endpoints: Managed Google MCP endpoint URLs for this agent.
        region: GCP region used to resolve region-parameterised endpoints
                (e.g., SecOps Chronicle).
        extra_custom_endpoints: Additional custom MCP endpoints (Action Broker,
                Org Context) that the agent is allowed to call.

    Returns:
        A list of McpToolset instances ready to be passed to the ADK agent constructor.

    Note:
        McpToolset uses Streamable HTTP transport with ADC-derived Bearer tokens.
        The credential flow uses google-auth's default credential chain —
        Application Default Credentials in Cloud Run / Agent Engine environments,
        and gcloud auth locally.

    ADK 2.0 API — confirm McpToolset constructor signature against adk.dev/2.0/ release notes
    """
    try:
        # ADK 2.0 import path — confirm against adk.dev/2.0/ release notes
        from google.adk.tools.mcp_tool import McpToolset  # type: ignore[import-untyped]
        from google.auth import default as google_auth_default  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "google-adk>=2.1 and google-auth are required. Run: pip install 'google-adk==2.1.*'"
        ) from exc

    credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

    all_endpoints = list(allowed_endpoints)
    if extra_custom_endpoints:
        all_endpoints.extend(extra_custom_endpoints)

    # Resolve region-parameterised endpoints
    resolved: list[str] = []
    for ep in all_endpoints:
        if "{region}" in ep:
            resolved.append(ep.format(region=region))
        else:
            resolved.append(ep)

    toolsets: list[McpToolset] = []
    for endpoint in resolved:
        # ADK 2.0 API — confirm McpToolset(endpoint, credentials, transport) signature
        toolset = McpToolset(
            endpoint=endpoint,
            credentials=credentials,
            transport="streamable_http",
        )
        toolsets.append(toolset)
        logger.debug("Wired MCP toolset: %s", endpoint)

    return toolsets
