"""Tests for the LlmAgent specialist builders (SRE / DevSecOps / Platform).

These mirror aop_finops: each constructs offline (toolsets injected) so an ADK
bump that breaks any specialist is caught in CI, not at deploy.
"""

from __future__ import annotations

import importlib

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


@pytest.mark.parametrize(
    ("module", "builder", "name"),
    [
        ("aop_sre.agent", "build_sre_agent", "sre_agent"),
        ("aop_devsecops.agent", "build_devsecops_agent", "devsecops_agent"),
        ("aop_platform.agent", "build_platform_agent", "platform_agent"),
    ],
)
def test_specialist_constructs_offline(module: str, builder: str, name: str) -> None:
    build = getattr(importlib.import_module(module), builder)
    agent = build(_settings(), toolsets=[])
    assert type(agent).__name__ == "LlmAgent"
    assert agent.name == name
