"""aop_finops.agent — FinOps Agent definition (ADK 2.3).

An ``LlmAgent`` with:
- MCP toolsets: billing-export BigQuery, Recommender, Action Broker (custom).
- System prompt from ``aop_finops.prompts``.

The agent proposes actions only via the Action Broker MCP (decision/execution
separation); it holds no write IAM.

Verified against google-adk 2.3.0 (see ``aop_common.models`` / ``aop_common.mcp_tools``).
A2A discovery-card registration is handled separately by the orchestrator hub and
is intentionally not wired here.
"""

from __future__ import annotations

import logging
from typing import Any

from aop_common.config import AopSettings
from aop_common.mcp_tools import FINOPS_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

from aop_finops.prompts import FINOPS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_finops_agent(settings: AopSettings, *, toolsets: list[Any] | None = None) -> Any:
    """Construct and return the FinOps ``LlmAgent``.

    Args:
        settings: Platform configuration (model id, region, MCP endpoints).
        toolsets: Pre-built MCP toolsets. When ``None`` (the deploy path) they are
            built from ``FINOPS_MCP_ENDPOINTS`` + the Action Broker endpoint, which
            requires credentials. Tests inject an explicit list (e.g. ``[]``) to
            construct the agent offline.

    Returns:
        A ``google.adk.agents.LlmAgent`` ready to register with Agent Engine.
    """
    from google.adk.agents import LlmAgent

    if toolsets is None:
        toolsets = build_mcp_toolsets(
            FINOPS_MCP_ENDPOINTS,
            region=settings.region,
            extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
        )

    model = ModelFactory.from_settings(settings).get_model()
    logger.info("build_finops_agent: model=%s tools=%d", settings.model_id, len(toolsets))

    return LlmAgent(
        name="finops_agent",
        model=model,
        instruction=FINOPS_SYSTEM_PROMPT,
        tools=toolsets,
    )
