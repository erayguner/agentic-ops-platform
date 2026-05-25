"""aop_sre.agent — ADK 2.0 SRE Agent definition.

LlmAgent with:
- Structured output schema: Finding v1
- MCP toolsets: Logging, Monitoring, Trace, Error Reporting, GKE,
  Cloud Run, Network Intelligence Center, Gemini Cloud Assist,
  Action Broker (custom)
- System prompt from sre.prompts

ADK 2.0 API — confirm LlmAgent constructor against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging

from aop_common.config import AopSettings
from aop_common.mcp_tools import SRE_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory
from aop_common.schemas import Finding
from aop_sre.prompts import SRE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_agent_card(settings: AopSettings) -> object:
    """Build the A2A AgentCard for the SRE Agent.

    ADK 2.0 API — confirm AgentCard / AgentSkill constructor against adk.dev/2.0/ release notes
    """
    try:
        from google.adk.a2a import AgentCard, AgentSkill  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("google-adk>=2.0 required") from exc

    return AgentCard(
        name="sre-agent",
        description=(
            "SRE specialist. Investigates latency, error rate, SLO burn, saturation, "
            "and deploy-related regressions. Produces Finding v1 with typed recommendations."
        ),
        model_id=settings.model_id,
        mcp_servers=SRE_MCP_ENDPOINTS + [settings.action_broker_mcp_endpoint],
        skills=[
            AgentSkill(
                name="investigate_reliability",
                description=(
                    "Receive an OpsSignal, query observability toolset, produce a "
                    "structured Finding with cause hypothesis, confidence, and recommendations."
                ),
            ),
        ],
    )


def build_sre_agent(settings: AopSettings) -> object:
    """Construct and return the ADK 2.0 SRE LlmAgent.

    The agent is configured with:
    - System prompt emphasising read-only investigation and structured output.
    - MCP toolsets for the SRE allow-list plus the Action Broker.
    - Structured output schema fixed to Finding (ops.finding.v1).
    - Model and fallback list from AopSettings.

    Returns:
        An ADK 2.0 LlmAgent instance.

    Raises:
        NotImplementedError: Skeleton — LlmAgent not wired.

    ADK 2.0 API — confirm LlmAgent(model, tools, system_prompt, output_schema, agent_card)
    constructor signature against adk.dev/2.0/ release notes
    """
    model_factory = ModelFactory.from_settings(settings)
    toolsets = build_mcp_toolsets(
        SRE_MCP_ENDPOINTS,
        region=settings.region,
        extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
    )
    agent_card = build_agent_card(settings)

    logger.info(
        "build_sre_agent: model=%s endpoint_count=%d",
        settings.model_id,
        len(toolsets),
    )

    # SKELETON: In production, wire ADK 2.0 LlmAgent, e.g.:
    #
    #   from google.adk.agents import LlmAgent
    #   return LlmAgent(
    #       model=model_factory.get_model(),
    #       tools=toolsets,
    #       system_prompt=SRE_SYSTEM_PROMPT,
    #       output_schema=Finding,   # structured JSON output enforced by ADK
    #       agent_card=agent_card,
    #   )

    raise NotImplementedError(
        "build_sre_agent is a skeleton. "
        "Wire the ADK 2.0 LlmAgent before deploying to Agent Engine."
    )
