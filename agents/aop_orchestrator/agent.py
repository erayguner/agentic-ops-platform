"""aop_orchestrator.agent — ADK 2.0 Ops Orchestrator definition.

Uses the ADK 2.0 graph-based Workflow Runtime. The workflow graph is:

    receive_signal
        └─► dedup
                └─► classify
                        └─► route  (fan-out: delegate to specialist via A2A)
                                └─► wait_for_finding
                                        └─► render_notification
                                                └─► [request_approval]  ← HITL node
                                                        └─► close

HITL node activates only when the finding includes a Tier 3/4 recommendation.

ADK 2.0 API — confirm WorkflowAgent / graph node API against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging

from aop_common.config import AopSettings
from aop_common.mcp_tools import ORCHESTRATOR_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# AgentCard (A2A)
# --------------------------------------------------------------------------- #


# ADK 2.0 API — confirm AgentCard / AgentSkill constructor against adk.dev/2.0/ release notes
def build_agent_card(settings: AopSettings) -> object:
    """Build the A2A AgentCard describing orchestrator capabilities.

    The card is used by peer agents to discover and delegate tasks via A2A.
    """
    try:
        from google.adk.a2a import AgentCard, AgentSkill  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("google-adk>=2.1 required") from exc

    return AgentCard(
        name="ops-orchestrator",
        description=(
            "Duty-manager orchestrator. Normalises, deduplicates, correlates and routes "
            "operational signals. Owns the Slack incident conversation. Manages HITL approval."
        ),
        model_id=settings.model_id,
        mcp_servers=[
            *ORCHESTRATOR_MCP_ENDPOINTS,
            settings.action_broker_mcp_endpoint,
            settings.org_context_mcp_endpoint,
        ],
        skills=[
            AgentSkill(
                name="route_signal",
                description="Receive, deduplicate, classify and route an OpsSignal.",
            ),
            AgentSkill(
                name="manage_incident",
                description="Open, update and close an incident in Firestore.",
            ),
            AgentSkill(
                name="request_approval",
                description="Initiate a Tier-3/4 HITL approval flow and relay the decision.",
            ),
        ],
    )


# --------------------------------------------------------------------------- #
# Workflow nodes
# --------------------------------------------------------------------------- #


def receive_signal_node(signal_data: dict) -> dict:
    """Node 1: receive and validate an OpsSignal from ops.signals.

    ADK 2.0 API — confirm node function signature against adk.dev/2.0/ release notes
    """
    from aop_common.schemas import OpsSignal

    signal = OpsSignal.model_validate(signal_data)
    logger.info("receive_signal: signal_id=%s source=%s", signal.signal_id, signal.source)
    return {"signal": signal, "status": "received"}


def dedup_node(state: dict) -> dict:
    """Node 2: deduplicate and correlate against open incidents in Firestore.

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
    """Node 3: classify severity and domain using the LLM.

    LLM call is skeletal — confidence and domain are placeholder values.
    ADK 2.0 API — confirm LLM invocation within a workflow node.
    """
    signal = state["signal"]
    logger.info("classify: signal_id=%s severity=%s", signal.signal_id, signal.severity)
    state["domain"] = "sre"  # SKELETON: LLM classification result
    state["confidence"] = 0.90  # SKELETON: LLM confidence score
    return state


def route_node(state: dict) -> dict:
    """Node 4: delegate to the appropriate specialist agent via A2A.

    SKELETON — A2A delegation not implemented.
    ADK 2.0 API — confirm A2A delegation within a workflow node.
    """
    domain = state.get("domain", "sre")
    logger.info("route: delegating to domain=%s", domain)
    state["routed_to"] = domain
    return state


def wait_for_finding_node(state: dict) -> dict:
    """Node 5: wait for the specialist's Finding (via ops.findings or A2A reply).

    SKELETON — Pub/Sub or A2A await not implemented.
    """
    logger.info("wait_for_finding: domain=%s", state.get("routed_to"))
    state["finding"] = None  # SKELETON: populated by specialist reply
    return state


def render_notification_node(state: dict) -> dict:
    """Node 6: render and publish an OpsNotification to ops.notifications.

    SKELETON — SlackEmitter.emit() not wired.
    """
    logger.info("render_notification: building OpsNotification")
    state["notification_emitted"] = False  # SKELETON: set True after emit
    return state


def request_approval_node(state: dict) -> dict:
    """Node 7 (HITL): publish ActionRequest and wait for Slack approval/rejection.

    This node activates only when the Finding contains a Tier 3 or Tier 4 recommendation.
    Default: if the approval window expires without a decision, the action is denied.

    SKELETON — HITL pause not implemented.
    ADK 2.0 API — confirm HITL / interrupt node API against adk.dev/2.0/ release notes
    """
    logger.info("request_approval: HITL node activated")
    state["approval_decision"] = None  # SKELETON: populated by Slack interactivity
    return state


def close_node(state: dict) -> dict:
    """Node 8: close the incident and emit the final AuditRecord."""
    logger.info("close: incident closed, correlation_id=%s", state.get("correlation_id"))
    state["status"] = "closed"
    return state


# --------------------------------------------------------------------------- #
# Routing logic (conditional edges)
# --------------------------------------------------------------------------- #


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


def build_orchestrator(settings: AopSettings) -> object:
    """Construct and return the ADK 2.0 Orchestrator WorkflowAgent.

    The graph topology:
        receive_signal → dedup → [drop if duplicate] → classify → route
            → wait_for_finding → render_notification
            → [request_approval (HITL) if Tier 3/4] → close

    Returns:
        An ADK 2.0 WorkflowAgent instance.

    Raises:
        NotImplementedError: Skeleton — WorkflowAgent wiring is not fully implemented.

    ADK 2.0 API — confirm WorkflowAgent / graph edge API against adk.dev/2.0/ release notes
    """
    ModelFactory.from_settings(settings)
    build_mcp_toolsets(
        ORCHESTRATOR_MCP_ENDPOINTS,
        region=settings.region,
        extra_custom_endpoints=[
            settings.action_broker_mcp_endpoint,
            settings.org_context_mcp_endpoint,
        ],
    )

    # SKELETON: Wire ADK 2.0 WorkflowAgent graph, e.g.:
    #
    #   from google.adk.agents import WorkflowAgent
    #   from google.adk.workflow import Graph, Node, Edge
    #
    #   graph = Graph()
    #   nodes = {
    #       "receive_signal": Node(fn=receive_signal_node),
    #       "dedup":          Node(fn=dedup_node),
    #       "classify":       Node(fn=classify_node),
    #       "route":          Node(fn=route_node),
    #       "wait_for_finding": Node(fn=wait_for_finding_node),
    #       "render_notification": Node(fn=render_notification_node),
    #       "request_approval": Node(fn=request_approval_node, hitl=True),
    #       "close":          Node(fn=close_node),
    #   }
    #   for name, node in nodes.items():
    #       graph.add_node(name, node)
    #
    #   graph.add_edge("receive_signal", "dedup")
    #   graph.add_edge("dedup", "classify", condition=lambda s: not _is_duplicate(s))
    #   graph.add_edge("dedup", "close",    condition=_is_duplicate)
    #   graph.add_edge("classify", "route")
    #   graph.add_edge("route", "wait_for_finding")
    #   graph.add_edge("wait_for_finding", "render_notification")
    #   graph.add_edge("render_notification", "request_approval", condition=_needs_approval)
    #   graph.add_edge("render_notification", "close",            condition=lambda s: not _needs_approval(s))
    #   graph.add_edge("request_approval", "close")
    #
    #   return WorkflowAgent(
    #       graph=graph,
    #       model=model_factory.get_model(),
    #       tools=toolsets,
    #       system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    #       agent_card=build_agent_card(settings),
    #   )

    raise NotImplementedError(
        "build_orchestrator is a skeleton. "
        "Wire the ADK 2.0 WorkflowAgent graph before deploying to Agent Engine."
    )
