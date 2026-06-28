"""Tests for aop_finops.agent — offline construction of the FinOps slice.

The FinOps agent is the first vertical slice wired against real ADK 2.3. The test
constructs it offline (toolsets injected) so a future ADK bump that breaks
construction is caught in CI.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

pytest.importorskip("google.adk")


def _settings() -> object:
    from aop_common.config import AopSettings

    return AopSettings(
        project="proj",
        agent_identity="sa-finops@proj.iam.gserviceaccount.com",
        action_broker_mcp_endpoint="https://broker.example/mcp",
        org_context_mcp_endpoint="https://orgctx.example/mcp",
    )


class TestFinopsAgent:
    def test_build_finops_agent_constructs_offline(self) -> None:
        from aop_finops.agent import build_finops_agent

        agent = build_finops_agent(_settings(), toolsets=[])
        assert type(agent).__name__ == "LlmAgent"
        assert agent.name == "finops_agent"
