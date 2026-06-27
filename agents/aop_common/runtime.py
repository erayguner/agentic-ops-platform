"""aop_common.runtime — the agent-runtime seam (keep the managed runtime swappable).

Why this module exists
----------------------
AOP deploys each agent to Vertex AI Agent Engine ("reasoning engines") through
the Vertex AI SDK. Two facts make that runtime the platform's highest-churn,
highest-commoditisation-risk surface:

  * Agent Engine is a fast-moving, partly-Preview API.
  * The agent *runtime* is exactly the layer a native GCP / hyperscaler offering
    is most likely to commoditise — at which point you want to re-base onto it
    without rewriting agent logic or the governance layer.

This module quarantines the entire Agent Engine API behind one ``AgentRuntime``
interface. Callers (``deployment/deploy.py`` today, a future re-base tomorrow)
depend only on the interface, never on a vendor type, so swapping the runtime is
a single-adapter change. The governance layer (Action Broker, policy client,
memory safeguards) is already runtime-agnostic and stays untouched.

``vertexai`` is imported lazily inside the adapter, so importing this module
costs nothing and needs no cloud credentials — the seam stays unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


def reasoning_engine_resource_name(project: str, region: str, agent: str) -> str:
    """Return the canonical Agent Engine resource name for an agent.

    Kept as a free function (not a vendor call) so callers can compute the
    expected resource name without importing any SDK.
    """
    return f"projects/{project}/locations/{region}/reasoningEngines/{agent}-agent"


@dataclass(frozen=True)
class DeployedAgent:
    """Runtime-agnostic handle returned by a deploy.

    Deliberately minimal: a ``resource_name`` is all a caller needs and all that
    every runtime can be expected to provide. Add fields only when a second
    adapter genuinely shares them.
    """

    resource_name: str


@runtime_checkable
class AgentRuntime(Protocol):
    """The swappable agent-runtime seam.

    An implementation takes a *built* agent object and deploys it, returning a
    :class:`DeployedAgent`. The interface intentionally carries no vendor type so
    that depending on it never drags in a specific SDK.
    """

    def deploy(
        self,
        *,
        agent: Any,
        requirements: list[str],
        extra_packages: list[str],
        display_name: str,
        description: str,
        service_account: str,
    ) -> DeployedAgent:
        """Deploy ``agent`` and return its runtime handle."""
        ...


class VertexAgentEngineRuntime:
    """:class:`AgentRuntime` backed by Vertex AI Agent Engine.

    The ONLY place the Vertex AI Agent Engine API (``vertexai.agent_engines``) is
    referenced. If GCP ships a native governed-ops runtime, or the SDK shape
    changes, replace or extend this adapter and leave the rest of the platform
    untouched.
    """

    def __init__(self, *, project: str, region: str, staging_bucket: str) -> None:
        self._project = project
        self._region = region
        self._staging_bucket = staging_bucket

    def deploy(
        self,
        *,
        agent: Any,
        requirements: list[str],
        extra_packages: list[str],
        display_name: str,
        description: str,
        service_account: str,
    ) -> DeployedAgent:
        # Lazy import: keeps module import cloud-free and credential-free.
        # Confirm the agent_engines.create() signature against the installed
        # google-cloud-aiplatform / google-adk version before first real use.
        import vertexai
        from vertexai import agent_engines

        vertexai.init(
            project=self._project,
            location=self._region,
            staging_bucket=self._staging_bucket,
        )
        remote_agent = agent_engines.create(
            agent_engine=agent,
            requirements=requirements,
            extra_packages=extra_packages,
            display_name=display_name,
            description=description,
            service_account=service_account,
        )
        return DeployedAgent(resource_name=remote_agent.resource_name)
