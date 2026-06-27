"""aop_orchestrator.agent — Ops Orchestrator definition (ADK 2.3).

The orchestrator is the duty-manager hub. ADK 2.3 has no graph ``WorkflowAgent``
(that API never shipped); the idiomatic realisation is an ``LlmAgent`` COORDINATOR
that routes a triaged signal to the right specialist via ``sub_agents``
(sre / devsecops / platform / finops).

The deterministic, non-LLM steps the original design drew as graph nodes
(dedup/correlate against Firestore, the Tier-3/4 HITL gate, incident close +
audit) are owned by the eventing + Action Broker layers — consistent with the
platform's decision/execution separation (the broker is the policy-gated,
HITL-capable executor). Those steps remain below as pure helper functions the
services layer drives; only the LLM routing lives in the agent.

Verified against google-adk 2.3.0. A2A discovery-card registration is deferred.
"""

from __future__ import annotations

import logging
from typing import Any

from aop_common.config import AopSettings
from aop_common.models import ModelFactory

from aop_orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Deterministic workflow steps — driven by the eventing + Action Broker layers,
# not by the LLM. Retained as the platform's deterministic-step library.
# --------------------------------------------------------------------------- #


def receive_signal_node(signal_data: dict) -> dict:
    """Step 1: receive and validate an OpsSignal from ops.signals."""
    from aop_common.schemas import OpsSignal

    signal = OpsSignal.model_validate(signal_data)
    logger.info("receive_signal: signal_id=%s source=%s", signal.signal_id, signal.source)
    return {"signal": signal, "status": "received"}


def dedup_node(state: dict) -> dict:
    """Step 2: deduplicate and correlate against open incidents in Firestore.

    Checks for: exact duplicate (source+source_ref), in-flight correlation_id,
    or same affected_component+severity within 15 minutes.
    SKELETON — Firestore query not implemented.
    """
    signal = state["signal"]
    logger.info("dedup: checking signal_id=%s", signal.signal_id)
    # SKELETON: query Firestore for open incidents
    state["deduplicated"] = True
    state["is_duplicate"] = False
    return state


def classify_node(state: dict) -> dict:
    """Step 3: classify severity and domain using the LLM.

    LLM call is skeletal — confidence and domain are placeholder values.
    """
    signal = state["signal"]
    logger.info("classify: signal_id=%s severity=%s", signal.signal_id, signal.severity)
    state["domain"] = "sre"  # SKELETON: LLM classification result
    state["confidence"] = 0.90  # SKELETON: LLM confidence score
    return state


def route_node(state: dict) -> dict:
    """Step 4: delegate to the appropriate specialist agent.

    SKELETON — delegation handled by the LlmAgent coordinator's sub_agents.
    """
    domain = state.get("domain", "sre")
    logger.info("route: delegating to domain=%s", domain)
    state["routed_to"] = domain
    return state


def wait_for_finding_node(state: dict) -> dict:
    """Step 5: wait for the specialist's Finding (via ops.findings).

    SKELETON — Pub/Sub await not implemented.
    """
    logger.info("wait_for_finding: domain=%s", state.get("routed_to"))
    state["finding"] = None  # SKELETON: populated by specialist reply
    return state


def render_notification_node(state: dict) -> dict:
    """Step 6: render and publish an OpsNotification to ops.notifications.

    SKELETON — SlackEmitter.emit() not wired.
    """
    logger.info("render_notification: building OpsNotification")
    state["notification_emitted"] = False  # SKELETON: set True after emit
    return state


def request_approval_node(state: dict) -> dict:
    """Step 7 (HITL): publish ActionRequest and wait for Slack approval/rejection.

    Activates only when the Finding contains a Tier 3 or Tier 4 recommendation.
    Default: if the approval window expires without a decision, the action is denied.
    SKELETON — HITL pause is owned by the Action Broker.
    """
    logger.info("request_approval: HITL step activated")
    state["approval_decision"] = None  # SKELETON: populated by Slack interactivity
    return state


def close_node(state: dict) -> dict:
    """Step 8: close the incident and emit the final AuditRecord."""
    logger.info("close: incident closed, correlation_id=%s", state.get("correlation_id"))
    state["status"] = "closed"
    return state


def _needs_approval(state: dict) -> bool:
    """Return True if the finding contains a Tier 3 or Tier 4 recommendation."""
    finding = state.get("finding")
    if finding is None:
        return False
    for rec in getattr(finding, "recommendations", []):
        if getattr(rec, "proposed_tier", 0) >= 3:
            return True
    return False


def _is_duplicate(state: dict) -> bool:
    return bool(state.get("is_duplicate", False))


# --------------------------------------------------------------------------- #
# Agent constructor
# --------------------------------------------------------------------------- #


def build_orchestrator(settings: AopSettings, *, sub_agents: list[Any] | None = None) -> Any:
    """Construct and return the orchestrator ``LlmAgent`` coordinator.

    The LLM routes a triaged signal to the right specialist via ``sub_agents``.
    When ``sub_agents`` is ``None`` (the deploy path) the four specialist agents
    are built and attached; tests inject an explicit list (e.g. ``[]``) to
    construct offline.
    """
    from google.adk.agents import LlmAgent

    if sub_agents is None:
        from aop_devsecops.agent import build_devsecops_agent
        from aop_finops.agent import build_finops_agent
        from aop_platform.agent import build_platform_agent
        from aop_sre.agent import build_sre_agent

        sub_agents = [
            build_sre_agent(settings),
            build_devsecops_agent(settings),
            build_platform_agent(settings),
            build_finops_agent(settings),
        ]

    model = ModelFactory.from_settings(settings).get_model()
    logger.info("build_orchestrator: model=%s sub_agents=%d", settings.model_id, len(sub_agents))

    return LlmAgent(
        name="orchestrator",
        model=model,
        instruction=ORCHESTRATOR_SYSTEM_PROMPT,
        sub_agents=sub_agents,
    )
