"""aop_platform.agent — Platform Engineering Agent definition (ADK 2.3).

An ``LlmAgent`` for platform health: configuration drift, IaC state, resource
hygiene, deployment health, and config compliance. Proposes actions only via the
Action Broker MCP (decision/execution separation); holds no write IAM.

Verified against google-adk 2.3.0 (mirrors ``aop_finops.agent``). A2A discovery-card
registration is handled separately by the orchestrator hub and is not wired here.
"""

from __future__ import annotations

import logging
from typing import Any

from aop_common.config import AopSettings
from aop_common.mcp_tools import PLATFORM_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

from aop_platform.prompts import PLATFORM_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_platform_agent(settings: AopSettings, *, toolsets: list[Any] | None = None) -> Any:
    """Construct and return the Platform Engineering ``LlmAgent``.

    ``toolsets`` defaults to the Platform MCP allow-list + the Action Broker
    (built at deploy time, needs credentials); tests inject an explicit list to
    construct offline. See ``aop_finops.agent.build_finops_agent`` for the pattern.
    """
    from google.adk.agents import LlmAgent

    if toolsets is None:
        toolsets = build_mcp_toolsets(
            PLATFORM_MCP_ENDPOINTS,
            region=settings.region,
            extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
        )

    model = ModelFactory.from_settings(settings).get_model()
    logger.info("build_platform_agent: model=%s tools=%d", settings.model_id, len(toolsets))

    return LlmAgent(
        name="platform_agent",
        model=model,
        instruction=PLATFORM_SYSTEM_PROMPT,
        tools=toolsets,
    )
