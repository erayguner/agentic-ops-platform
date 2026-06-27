"""ADK churn guardrails — smoke tests that go red when a google-adk bump breaks
the platform's integration surface.

The agents are still skeletons, so these do NOT exercise real ADK behaviour.
They lock down the things that *can* be checked today and that an ADK version
bump is most likely to break:

  * the runtime seam (``aop_common.runtime``) stays cloud-free and swappable,
  * the deploy CLI's dry-run + Agent Engine region guard still work,
  * the ModelFactory's non-ADK surface is stable,
  * the ADK import paths the code depends on still resolve (xfail until Phase 1
    wires the real agents and verifies them — an XPASS then flags them as
    confirmed).

These run under the existing ``pytest (agents)`` CI job, so a Dependabot ADK
bump (isolated into its own PR — see .github/dependabot.yml) turns these red on
breakage instead of a production deploy.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_DEPLOY = Path(__file__).parent.parent / "deployment" / "deploy.py"

# The ADK 2.x import paths the codebase binds to. These are currently
# unverified guesses (every call site is annotated "confirm against release
# notes"), so the surface test is xfail until Phase 1 verifies them against a
# real build.
_ADK_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("google.adk.agents", "LlmAgent"),
    ("google.adk.agents", "WorkflowAgent"),
    ("google.adk.a2a", "AgentCard"),
    ("google.adk.a2a", "AgentSkill"),
    ("google.adk.tools.mcp_tool", "McpToolset"),
    ("google.adk.models", "LlmModel"),
)


def _adk_installed() -> bool:
    try:
        return importlib.util.find_spec("google.adk") is not None
    except ModuleNotFoundError:
        return False


# --------------------------------------------------------------------------- #
# Runtime seam (aop_common.runtime) — Gap 2: keep the runtime swappable
# --------------------------------------------------------------------------- #


class TestRuntimeSeam:
    def test_resource_name_format(self) -> None:
        from aop_common.runtime import reasoning_engine_resource_name

        assert (
            reasoning_engine_resource_name("proj", "us-central1", "finops")
            == "projects/proj/locations/us-central1/reasoningEngines/finops-agent"
        )

    def test_adapter_satisfies_protocol(self) -> None:
        from aop_common.runtime import AgentRuntime, VertexAgentEngineRuntime

        runtime = VertexAgentEngineRuntime(
            project="p", region="us-central1", staging_bucket="gs://b"
        )
        assert isinstance(runtime, AgentRuntime)

    def test_constructing_adapter_does_not_import_sdk(self) -> None:
        # The seam must stay cloud-free: constructing the adapter must not pull
        # in vertexai. Pop first so the assertion is deterministic regardless of
        # test order.
        sys.modules.pop("vertexai", None)
        from aop_common.runtime import VertexAgentEngineRuntime

        VertexAgentEngineRuntime(project="p", region="us-central1", staging_bucket="gs://b")
        assert "vertexai" not in sys.modules


# --------------------------------------------------------------------------- #
# Deploy CLI — Gap 1/4: dry-run + Agent Engine region guard
# --------------------------------------------------------------------------- #


class TestDeployCli:
    def test_dry_run_exits_clean(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(_DEPLOY),
                "--agent",
                "finops",
                "--project",
                "p",
                "--region",
                "us-central1",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "DRY RUN" in result.stdout

    def test_unsupported_region_is_rejected(self) -> None:
        # europe-west2 (the platform default) does NOT support Agent Engine —
        # the guard must fail fast rather than attempt a billable deploy.
        result = subprocess.run(
            [
                sys.executable,
                str(_DEPLOY),
                "--agent",
                "finops",
                "--project",
                "p",
                "--region",
                "europe-west2",
                "--execute",
                "--staging-bucket",
                "gs://b",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "does not support" in result.stderr


# --------------------------------------------------------------------------- #
# Model factory — Gap 4: non-ADK surface stable, ADK construction still stubbed
# --------------------------------------------------------------------------- #


class TestModelFactory:
    def test_factory_carries_config_without_constructing_model(self) -> None:
        from aop_common.models import ModelFactory

        factory = ModelFactory(model_id="gemini-3-pro", fallback_list=["gemini-2-flash"])
        # Skeleton convention (cf. test_triage): the ADK construction is stubbed.
        with pytest.raises(NotImplementedError):
            factory.get_model()


# --------------------------------------------------------------------------- #
# ADK import surface — Gap 4: early-warning for ADK API churn
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not _adk_installed(), reason="google-adk not installed")
@pytest.mark.xfail(
    reason="ADK 2.x import paths are unverified until Phase 1 wires real agents",
    strict=False,
)
@pytest.mark.parametrize(("module", "symbol"), _ADK_SYMBOLS)
def test_adk_symbol_resolves(module: str, symbol: str) -> None:
    mod = importlib.import_module(module)
    assert hasattr(mod, symbol)
