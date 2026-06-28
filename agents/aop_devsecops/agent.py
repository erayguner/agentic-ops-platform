"""aop_devsecops.agent — DevSecOps Agent definition (ADK 2.3).

An ``LlmAgent`` for security posture: SCC findings, IAM drift, key exposure,
supply-chain risk, and Model Armor signals. Proposes actions only via the Action
Broker MCP (decision/execution separation); holds no write IAM.

Verified against google-adk 2.3.0 (mirrors ``aop_finops.agent``). A2A discovery-card
registration is handled separately by the orchestrator hub and is not wired here.
"""

from __future__ import annotations

import logging
from typing import Any

from aop_common.config import AopSettings
from aop_common.mcp_tools import DEVSECOPS_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

from aop_devsecops.prompts import DEVSECOPS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_devsecops_agent(settings: AopSettings, *, toolsets: list[Any] | None = None) -> Any:
    """Construct and return the DevSecOps ``LlmAgent``.

    ``toolsets`` defaults to the DevSecOps MCP allow-list + the Action Broker
    (built at deploy time, needs credentials); tests inject an explicit list to
    construct offline. See ``aop_finops.agent.build_finops_agent`` for the pattern.
    """
    from google.adk.agents import LlmAgent

    if toolsets is None:
        toolsets = build_mcp_toolsets(
            DEVSECOPS_MCP_ENDPOINTS,
            region=settings.region,
            extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
        )

    model = ModelFactory.from_settings(settings).get_model()
    logger.info("build_devsecops_agent: model=%s tools=%d", settings.model_id, len(toolsets))

    return LlmAgent(
        name="devsecops_agent",
        model=model,
        instruction=DEVSECOPS_SYSTEM_PROMPT,
        tools=toolsets,
    )
