"""aop_decommission.agent — ADK 2.0 Decommission Agent definition.

A campaign agent built on the ADK 2.0 graph Workflow Runtime — the same pattern
as the orchestrator — because decommissioning is inherently multi-step and
gated. The graph is:

    discover → inventory → plan → [request_approval]  ← HITL gate (destructive)
                                        └─► execute → validate → report → close

The plan → execute edge only fires after explicit approval, and ``execute`` only
ever *proposes* to the Action Broker (the node functions call
``aop_decommission.campaign``, never a cloud delete API). The real engine logic
lives in the sibling modules and is fully unit-tested; this file is the ADK
wiring skeleton, consistent with the other agents — ``build_decommission_agent``
raises ``NotImplementedError`` until the WorkflowAgent graph is bound.

ADK 2.0 API — confirm WorkflowAgent / graph node API against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging
from typing import Any

from aop_common.config import AopSettings
from aop_common.mcp_tools import DECOMMISSION_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# AgentCard (A2A)
# --------------------------------------------------------------------------- #


def build_agent_card(settings: AopSettings) -> object:
    """Build the A2A AgentCard for the Decommission Agent.

    ADK 2.0 API — confirm AgentCard / AgentSkill constructor against adk.dev/2.0/ release notes
    """
    try:
        from google.adk.a2a import AgentCard, AgentSkill  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("google-adk>=2.1 required") from exc

    return AgentCard(
        name="decommission-agent",
        description=(
            "Project-closure specialist. Inventories the estate, applies the exemption "
            "policy, produces a dependency-ordered dry-run teardown plan, and — on "
            "approval — proposes each destroy to the Action Broker, then validates and "
            "reports closure readiness. Read-only IAM; never deletes directly. "
            "Produces Finding v1 + DecommissionReport."
        ),
        model_id=settings.model_id,
        mcp_servers=[*DECOMMISSION_MCP_ENDPOINTS, settings.action_broker_mcp_endpoint],
        skills=[
            AgentSkill(
                name="inventory_estate",
                description="Discover and classify every resource in the target project.",
            ),
            AgentSkill(
                name="plan_decommission",
                description="Produce a dependency-ordered dry-run plan honouring exemptions.",
            ),
            AgentSkill(
                name="execute_decommission",
                description="Propose approved teardown to the Action Broker, then validate.",
            ),
        ],
    )


# --------------------------------------------------------------------------- #
# Workflow nodes — drive aop_decommission.campaign. The pure stages (plan,
# report) run real engine code; discover/execute need live MCP + Broker and are
# skeletal until those clients are injected.
# --------------------------------------------------------------------------- #


def discover_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 1: inventory the estate via the read-only discovery MCP allow-list.

    SKELETON — wire InventoryScanner providers (TerraformStateSource from the CI
    `terraform show -json`, AssetInventorySource from the Asset Inventory MCP).
    """
    logger.info("discover: scanning project=%s", state.get("project"))
    state["inventory"] = None  # SKELETON: populated by InventoryScanner.scan()
    return state


def plan_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 2: apply exemptions and build the dependency-ordered dry-run plan.

    Pure engine code — runs ``Planner.plan`` against the inventory + policy once
    ``discover`` is wired.
    """
    logger.info("plan: building decommission plan for project=%s", state.get("project"))
    state["plan"] = None  # SKELETON: Planner.plan(inventory.resources, policy, ...)
    return state


def request_approval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 3 (HITL): pause for human approval before any destructive stage.

    Activates whenever the plan contains delete actions. The OpsNotification is
    emitted with human_required=true; teardown proceeds only on approval.
    SKELETON — HITL pause not implemented.
    """
    logger.info("request_approval: HITL gate before teardown")
    state["approved"] = False  # SKELETON: populated by the Slack approval flow
    return state


def execute_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 4: propose teardown to the Action Broker, stage by stage.

    SKELETON — wire DecommissionExecutor with an ActionBrokerClient-backed
    proposer. No cloud delete is ever called here; only propose_action.
    """
    logger.info("execute: proposing teardown via Action Broker")
    state["execution"] = None  # SKELETON: DecommissionExecutor.execute(plan)
    return state


def validate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 5: re-scan and validate closure readiness."""
    logger.info("validate: re-scanning estate for residual resources")
    state["validation"] = None  # SKELETON: Validator.validate(plan, post_inventory)
    return state


def report_node(state: dict[str, Any]) -> dict[str, Any]:
    """Node 6: assemble and emit the final DecommissionReport."""
    logger.info("report: assembling closure-readiness report")
    state["report"] = None  # SKELETON: report.build_report(...)
    return state


def _has_deletions(state: dict[str, Any]) -> bool:
    """True if the plan contains at least one delete action (gates the HITL node)."""
    plan = state.get("plan")
    return bool(plan is not None and getattr(plan, "to_delete", 0) > 0)


# --------------------------------------------------------------------------- #
# Agent constructor
# --------------------------------------------------------------------------- #


def build_decommission_agent(settings: AopSettings) -> object:
    """Construct and return the ADK 2.0 Decommission WorkflowAgent.

    Returns:
        An ADK 2.0 WorkflowAgent instance.

    Raises:
        NotImplementedError: Skeleton — WorkflowAgent wiring is not fully implemented.

    ADK 2.0 API — confirm WorkflowAgent / graph edge API against adk.dev/2.0/ release notes
    """
    ModelFactory.from_settings(settings)
    build_mcp_toolsets(
        DECOMMISSION_MCP_ENDPOINTS,
        region=settings.region,
        extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
    )
    build_agent_card(settings)

    # SKELETON: Wire ADK 2.0 WorkflowAgent graph, e.g.:
    #
    #   from google.adk.agents import WorkflowAgent
    #   from google.adk.workflow import Graph, Node
    #
    #   graph = Graph()
    #   graph.add_node("discover", Node(fn=discover_node))
    #   graph.add_node("plan", Node(fn=plan_node))
    #   graph.add_node("request_approval", Node(fn=request_approval_node, hitl=True))
    #   graph.add_node("execute", Node(fn=execute_node))
    #   graph.add_node("validate", Node(fn=validate_node))
    #   graph.add_node("report", Node(fn=report_node))
    #   graph.add_edge("discover", "plan")
    #   graph.add_edge("plan", "request_approval", condition=_has_deletions)
    #   graph.add_edge("plan", "report",           condition=lambda s: not _has_deletions(s))
    #   graph.add_edge("request_approval", "execute", condition=lambda s: s.get("approved"))
    #   graph.add_edge("request_approval", "report",  condition=lambda s: not s.get("approved"))
    #   graph.add_edge("execute", "validate")
    #   graph.add_edge("validate", "report")
    #
    #   return WorkflowAgent(
    #       graph=graph,
    #       model=model_factory.get_model(),
    #       tools=toolsets,
    #       system_prompt=DECOMMISSION_SYSTEM_PROMPT,
    #       output_schema=Finding,
    #       agent_card=build_agent_card(settings),
    #   )

    raise NotImplementedError(
        "build_decommission_agent is a skeleton. "
        "Wire the ADK 2.0 WorkflowAgent graph before deploying to Agent Engine."
    )
