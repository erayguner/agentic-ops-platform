"""ADK churn guardrails — smoke tests that go red when a google-adk bump breaks
the platform's integration surface.

These run under the existing ``pytest (agents)`` CI job, so a Dependabot ADK
bump (isolated into its own PR — see .github/dependabot.yml) turns these red on
breakage instead of a production deploy.

Import paths were verified against the installed google-adk (2.3.0). The ADK 2.x
API differs from the original skeletons' guesses, captured here so drift is
caught automatically:

  * workflow primitives are ``SequentialAgent`` / ``LoopAgent`` (no ``WorkflowAgent``),
  * the model class is ``Gemini`` in ``google.adk.models.google_llm`` (no ``LlmModel``),
  * ``McpToolset`` takes a ``StreamableHTTPConnectionParams`` (no endpoint/transport
    kwargs) and requires the ``google-adk[mcp]`` extra (declared in pyproject).
    A2A wiring is deferred — best done with the orchestrator, the A2A hub.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# google.adk emits an [EXPERIMENTAL] UserWarning on import; it is not a defect.
pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

_DEPLOY = Path(__file__).parent.parent / "deployment" / "deploy.py"


def _adk_installed() -> bool:
    try:
        return importlib.util.find_spec("google.adk") is not None
    except ModuleNotFoundError:
        return False


# Verified-correct import paths the platform binds to (hard assertions — a bump
# that moves any of these turns the suite red). Includes the [mcp] extra the
# platform declares.
_VERIFIED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("google.adk.agents", "LlmAgent"),
    ("google.adk.agents", "SequentialAgent"),
    ("google.adk.agents", "LoopAgent"),
    ("google.adk.models", "BaseLlm"),
    ("google.adk.models", "LLMRegistry"),
    ("google.adk.models.google_llm", "Gemini"),
    ("google.adk.tools.mcp_tool", "McpToolset"),
    ("google.adk.tools.mcp_tool", "StreamableHTTPConnectionParams"),
)


# --------------------------------------------------------------------------- #
# Runtime seam (aop_common.runtime) — keep the runtime swappable
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
        # The seam must stay cloud-free: constructing the adapter must not pull in
        # vertexai. Pop first so the assertion is deterministic regardless of order.
        sys.modules.pop("vertexai", None)
        from aop_common.runtime import VertexAgentEngineRuntime

        VertexAgentEngineRuntime(project="p", region="us-central1", staging_bucket="gs://b")
        assert "vertexai" not in sys.modules


# --------------------------------------------------------------------------- #
# Deploy CLI — dry-run + Agent Engine region guard
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
        # europe-west2 (the platform default) does NOT support Agent Engine — the
        # guard must fail fast rather than attempt a billable deploy.
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
# Model factory — now real: constructs a Gemini model offline (no creds)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not _adk_installed(), reason="google-adk not installed")
class TestModelFactory:
    def test_get_model_constructs_gemini_and_caches(self) -> None:
        from aop_common.models import ModelFactory

        factory = ModelFactory(model_id="gemini-3-pro", fallback_list=["gemini-3.5-flash"])
        model = factory.get_model()
        assert type(model).__name__ == "Gemini"
        assert factory.get_model() is model  # cached on second call


# --------------------------------------------------------------------------- #
# MCP endpoint resolution — pure helper, testable without the SDK or creds
# --------------------------------------------------------------------------- #


class TestMcpEndpointResolution:
    def test_appends_custom_and_formats_region(self) -> None:
        from aop_common.mcp_tools import resolve_mcp_endpoints

        resolved = resolve_mcp_endpoints(
            [
                "https://logging.googleapis.com/mcp",
                "https://chronicle.{region}.rep.googleapis.com/mcp",
            ],
            ["https://broker.example/mcp"],
            region="europe-west1",
        )
        assert resolved == [
            "https://logging.googleapis.com/mcp",
            "https://chronicle.europe-west1.rep.googleapis.com/mcp",
            "https://broker.example/mcp",
        ]


# --------------------------------------------------------------------------- #
# ADK import surface — early-warning for API churn
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not _adk_installed(), reason="google-adk not installed")
@pytest.mark.parametrize(("module", "symbol"), _VERIFIED_IMPORTS)
def test_verified_import_resolves(module: str, symbol: str) -> None:
    mod = importlib.import_module(module)
    assert hasattr(mod, symbol), f"{module}.{symbol} missing — ADK API drift"
