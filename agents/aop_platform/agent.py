"""aop_platform.agent — ADK 2.0 Platform Engineering Agent definition.

LlmAgent with:
- Structured output schema: Finding v1
- MCP toolsets: Cloud Asset Inventory, Resource Manager, GKE, Cloud Run,
  Compute, Action Broker (custom)
- System prompt from platform.prompts

ADK 2.0 API — confirm LlmAgent constructor against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging

from aop_common.config import AopSettings
from aop_common.mcp_tools import PLATFORM_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

logger = logging.getLogger(__name__)


def build_agent_card(settings: AopSettings) -> object:
    """Build the A2A AgentCard for the Platform Engineering Agent.

    ADK 2.0 API — confirm AgentCard / AgentSkill constructor against adk.dev/2.0/ release notes
    """
    try:
        from google.adk.a2a import AgentCard, AgentSkill  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("google-adk>=2.1 required") from exc

    return AgentCard(
        name="platform-agent",
        description=(
            "Platform Engineering specialist. Investigates configuration drift, "
            "IaC state, resource hygiene, and deployment health. Produces Finding v1."
        ),
        model_id=settings.model_id,
        mcp_servers=[*PLATFORM_MCP_ENDPOINTS, settings.action_broker_mcp_endpoint],
        skills=[
            AgentSkill(
                name="investigate_drift",
                description=(
                    "Receive an OpsSignal, query Asset Inventory and Resource Manager "
                    "for drift vs. declared state; produce a structured Finding."
                ),
            ),
            AgentSkill(
                name="assess_deployment_health",
                description=(
                    "Review GKE / Cloud Run / Cloud Deploy state and emit a Finding "
                    "with deployment health assessment."
                ),
            ),
        ],
    )


def build_platform_agent(settings: AopSettings) -> object:
    """Construct and return the ADK 2.0 Platform Engineering LlmAgent.

    Cloud Asset Inventory MCP is Preview — if unavailable, the agent falls
    back to BigQuery-exported asset data via the BigQuery MCP.

    Returns:
        An ADK 2.0 LlmAgent instance.

    Raises:
        NotImplementedError: Skeleton — LlmAgent not wired.

    ADK 2.0 API — confirm LlmAgent constructor signature against adk.dev/2.0/ release notes
    """
    ModelFactory.from_settings(settings)
    toolsets = build_mcp_toolsets(
        PLATFORM_MCP_ENDPOINTS,
        region=settings.region,
        extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
    )
    build_agent_card(settings)

    logger.info(
        "build_platform_agent: model=%s endpoint_count=%d",
        settings.model_id,
        len(toolsets),
    )

    # SKELETON: In production, wire ADK 2.0 LlmAgent, e.g.:
    #
    #   from google.adk.agents import LlmAgent
    #   return LlmAgent(
    #       model=model_factory.get_model(),
    #       tools=toolsets,
    #       system_prompt=PLATFORM_SYSTEM_PROMPT,
    #       output_schema=Finding,
    #       agent_card=agent_card,
    #   )

    raise NotImplementedError(
        "build_platform_agent is a skeleton. "
        "Wire the ADK 2.0 LlmAgent before deploying to Agent Engine."
    )
