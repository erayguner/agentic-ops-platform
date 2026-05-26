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
# Managed MCP endpoint constants (§4.2 of INTERFACE-CONTRACT, §2.7 DESIGN-REVIEW)
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
DEVELOPER_KNOWLEDGE_MCP = "https://developerknowledge.googleapis.com/mcp"  # GA — Google developer documentation lookup

# Per-agent allow-lists (§4.2 INTERFACE-CONTRACT / §4.2 DESIGN-REVIEW)
ORCHESTRATOR_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    PUBSUB_MCP,
    RESOURCE_MANAGER_MCP,
]

SRE_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    MONITORING_MCP,
    TRACE_MCP,
    ERROR_REPORTING_MCP,
    GKE_MCP,
    CLOUD_RUN_MCP,
    NETWORK_INTELLIGENCE_MCP,
    GEMINI_CLOUD_ASSIST_MCP,
    DEVELOPER_KNOWLEDGE_MCP,
]

DEVSECOPS_MCP_ENDPOINTS: list[str] = [
    LOGGING_MCP,
    ASSET_INVENTORY_MCP,
    RESOURCE_MANAGER_MCP,
    COMPUTE_MCP,
    DEVELOPER_KNOWLEDGE_MCP,
    # SecOps endpoint is region-parameterised; resolved at runtime via build_mcp_toolsets
]

PLATFORM_MCP_ENDPOINTS: list[str] = [
    ASSET_INVENTORY_MCP,
    RESOURCE_MANAGER_MCP,
    GKE_MCP,
    CLOUD_RUN_MCP,
    COMPUTE_MCP,
    DEVELOPER_KNOWLEDGE_MCP,
]

FINOPS_MCP_ENDPOINTS: list[str] = [
    BIGQUERY_MCP,
    RECOMMENDER_MCP,
    GEMINI_CLOUD_ASSIST_MCP,
    DEVELOPER_KNOWLEDGE_MCP,
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
            "google-adk>=2.0 and google-auth are required. " "Run: pip install 'google-adk==2.0.*'"
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
