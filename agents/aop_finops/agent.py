"""aop_finops.agent — ADK 2.0 FinOps Agent definition.

LlmAgent with:
- Structured output schema: Finding v1
- MCP toolsets: BigQuery (billing export), Recommender, Gemini Cloud Assist,
  Action Broker (custom)
- System prompt from finops.prompts

ADK 2.0 API — confirm LlmAgent constructor against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging

from aop_common.config import AopSettings
from aop_common.mcp_tools import FINOPS_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

logger = logging.getLogger(__name__)


def build_agent_card(settings: AopSettings) -> object:
    """Build the A2A AgentCard for the FinOps Agent.

    ADK 2.0 API — confirm AgentCard / AgentSkill constructor against adk.dev/2.0/ release notes
    """
    try:
        from google.adk.a2a import AgentCard, AgentSkill  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("google-adk>=2.0 required") from exc

    return AgentCard(
        name="finops-agent",
        description=(
            "FinOps specialist. Monitors cost anomalies, budget burn, waste, and "
            "rightsizing opportunities. Wraps Gemini Cloud Assist FinOps where available. "
            "Produces Finding v1."
        ),
        model_id=settings.model_id,
        mcp_servers=FINOPS_MCP_ENDPOINTS + [settings.action_broker_mcp_endpoint],
        skills=[
            AgentSkill(
                name="investigate_cost_anomaly",
                description=(
                    "Query billing export BigQuery, Recommender, and Gemini Cloud Assist "
                    "FinOps agent; produce a structured Finding with cost impact and "
                    "rightsizing recommendations."
                ),
            ),
        ],
    )


def build_finops_agent(settings: AopSettings) -> object:
    """Construct and return the ADK 2.0 FinOps LlmAgent.

    Gemini Cloud Assist MCP is Preview — the agent degrades gracefully to
    BigQuery + Recommender-only analysis when the MCP is unavailable.

    Returns:
        An ADK 2.0 LlmAgent instance.

    Raises:
        NotImplementedError: Skeleton — LlmAgent not wired.

    ADK 2.0 API — confirm LlmAgent constructor signature against adk.dev/2.0/ release notes
    """
    ModelFactory.from_settings(settings)
    toolsets = build_mcp_toolsets(
        FINOPS_MCP_ENDPOINTS,
        region=settings.region,
        extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
    )
    build_agent_card(settings)

    logger.info(
        "build_finops_agent: model=%s endpoint_count=%d",
        settings.model_id,
        len(toolsets),
    )

    # SKELETON: In production, wire ADK 2.0 LlmAgent, e.g.:
    #
    #   from google.adk.agents import LlmAgent
    #   return LlmAgent(
    #       model=model_factory.get_model(),
    #       tools=toolsets,
    #       system_prompt=FINOPS_SYSTEM_PROMPT,
    #       output_schema=Finding,
    #       agent_card=agent_card,
    #   )

    raise NotImplementedError(
        "build_finops_agent is a skeleton. "
        "Wire the ADK 2.0 LlmAgent before deploying to Agent Engine."
    )
