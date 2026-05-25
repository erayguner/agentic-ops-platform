"""aop_devsecops.agent — ADK 2.0 DevSecOps Agent definition.

LlmAgent with:
- Structured output schema: Finding v1
- MCP toolsets: SecOps (Chronicle), Cloud Asset Inventory, Resource Manager,
  Cloud Logging, Compute, Action Broker (custom)
- System prompt from devsecops.prompts

ADK 2.0 API — confirm LlmAgent constructor against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging

from aop_common.config import AopSettings
from aop_common.mcp_tools import (
    DEVSECOPS_MCP_ENDPOINTS,
    SECOPS_MCP_TEMPLATE,
    build_mcp_toolsets,
)
from aop_common.models import ModelFactory

logger = logging.getLogger(__name__)


def build_agent_card(settings: AopSettings) -> object:
    """Build the A2A AgentCard for the DevSecOps Agent.

    ADK 2.0 API — confirm AgentCard / AgentSkill constructor against adk.dev/2.0/ release notes
    """
    try:
        from google.adk.a2a import AgentCard, AgentSkill  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("google-adk>=2.0 required") from exc

    secops_ep = SECOPS_MCP_TEMPLATE.format(region=settings.region)
    return AgentCard(
        name="devsecops-agent",
        description=(
            "DevSecOps specialist. Investigates SCC findings, IAM drift, key exposure, "
            "vulnerability signals, and policy violations. Produces Finding v1."
        ),
        model_id=settings.model_id,
        mcp_servers=DEVSECOPS_MCP_ENDPOINTS
        + [secops_ep, settings.action_broker_mcp_endpoint],
        skills=[
            AgentSkill(
                name="investigate_security",
                description=(
                    "Receive an OpsSignal, query SecOps/Chronicle, Asset Inventory, "
                    "and audit logs; produce a structured Finding with risk assessment "
                    "and typed recommendations."
                ),
            ),
        ],
    )


def build_devsecops_agent(settings: AopSettings) -> object:
    """Construct and return the ADK 2.0 DevSecOps LlmAgent.

    The SecOps MCP endpoint is region-parameterised:
        https://chronicle.<region>.rep.googleapis.com/mcp

    The allow-list also includes Cloud Asset Inventory (Preview) behind a
    feature flag — falls back to BigQuery-exported asset data if unavailable.

    Returns:
        An ADK 2.0 LlmAgent instance.

    Raises:
        NotImplementedError: Skeleton — LlmAgent not wired.

    ADK 2.0 API — confirm LlmAgent constructor signature against adk.dev/2.0/ release notes
    """
    ModelFactory.from_settings(settings)
    secops_ep = SECOPS_MCP_TEMPLATE.format(region=settings.region)
    toolsets = build_mcp_toolsets(
        DEVSECOPS_MCP_ENDPOINTS + [secops_ep],
        region=settings.region,
        extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
    )
    build_agent_card(settings)

    logger.info(
        "build_devsecops_agent: model=%s endpoint_count=%d secops_region=%s",
        settings.model_id,
        len(toolsets),
        settings.region,
    )

    # SKELETON: In production, wire ADK 2.0 LlmAgent, e.g.:
    #
    #   from google.adk.agents import LlmAgent
    #   return LlmAgent(
    #       model=model_factory.get_model(),
    #       tools=toolsets,
    #       system_prompt=DEVSECOPS_SYSTEM_PROMPT,
    #       output_schema=Finding,
    #       agent_card=agent_card,
    #   )

    raise NotImplementedError(
        "build_devsecops_agent is a skeleton. "
        "Wire the ADK 2.0 LlmAgent before deploying to Agent Engine."
    )
