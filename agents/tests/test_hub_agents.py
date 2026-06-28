"""Offline construction of the orchestrator (LlmAgent coordinator) and the
decommission agent against real ADK 2.3.

Both realise their original graph-WorkflowAgent design as ADK 2.3 LlmAgents — the
orchestrator with specialist ``sub_agents``, decommission as a read-only proposer.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

pytest.importorskip("google.adk")


def _settings() -> object:
    from aop_common.config import AopSettings

    return AopSettings(
        project="proj",
        agent_identity="sa@proj.iam.gserviceaccount.com",
        action_broker_mcp_endpoint="https://broker.example/mcp",
        org_context_mcp_endpoint="https://orgctx.example/mcp",
    )


def test_orchestrator_constructs_offline() -> None:
    from aop_orchestrator.agent import build_orchestrator

    agent = build_orchestrator(_settings(), sub_agents=[])
    assert type(agent).__name__ == "LlmAgent"
    assert agent.name == "orchestrator"


def test_decommission_constructs_offline() -> None:
    from aop_decommission.agent import build_decommission_agent

    agent = build_decommission_agent(_settings(), toolsets=[])
    assert type(agent).__name__ == "LlmAgent"
    assert agent.name == "decommission_agent"
