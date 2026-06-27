"""aop_decommission.agent — Decommission Agent definition (ADK 2.3).

A project-closure agent. ADK 2.3 has no graph ``WorkflowAgent``; the agent is
realised as a read-only ``LlmAgent`` (like the specialists) that *proposes* every
teardown to the Action Broker — it holds read-only IAM and never calls a cloud
delete API. The multi-step campaign (discover → plan → [HITL gate] → execute →
validate → report) is the platform's deterministic-step library below, driven by
the eventing + Action Broker layers; the destructive HITL gate is the broker's.
The real engine logic lives in the sibling ``aop_decommission`` modules and is
fully unit-tested.

Verified against google-adk 2.3.0. A2A discovery-card registration is deferred.
"""

from __future__ import annotations

import logging
from typing import Any

from aop_common.config import AopSettings
from aop_common.mcp_tools import DECOMMISSION_MCP_ENDPOINTS, build_mcp_toolsets
from aop_common.models import ModelFactory

from aop_decommission.prompts import DECOMMISSION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Deterministic campaign steps — drive aop_decommission.campaign. The pure stages
# (plan, report) run real engine code; discover/execute need live MCP + Broker
# and are skeletal until those clients are injected.
# --------------------------------------------------------------------------- #


def discover_node(state: dict[str, Any]) -> dict[str, Any]:
    """Step 1: inventory the estate via the read-only discovery MCP allow-list.

    SKELETON — wire InventoryScanner providers (TerraformStateSource from the CI
    `terraform show -json`, AssetInventorySource from the Asset Inventory MCP).
    """
    logger.info("discover: scanning project=%s", state.get("project"))
    state["inventory"] = None  # SKELETON: populated by InventoryScanner.scan()
    return state


def plan_node(state: dict[str, Any]) -> dict[str, Any]:
    """Step 2: apply exemptions and build the dependency-ordered dry-run plan.

    Pure engine code — runs ``Planner.plan`` against the inventory + policy once
    ``discover`` is wired.
    """
    logger.info("plan: building decommission plan for project=%s", state.get("project"))
    state["plan"] = None  # SKELETON: Planner.plan(inventory.resources, policy, ...)
    return state


def request_approval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Step 3 (HITL): pause for human approval before any destructive stage.

    Activates whenever the plan contains delete actions. The OpsNotification is
    emitted with human_required=true; teardown proceeds only on approval.
    SKELETON — HITL pause is owned by the Action Broker.
    """
    logger.info("request_approval: HITL gate before teardown")
    state["approved"] = False  # SKELETON: populated by the Slack approval flow
    return state


def execute_node(state: dict[str, Any]) -> dict[str, Any]:
    """Step 4: propose teardown to the Action Broker, stage by stage.

    SKELETON — wire DecommissionExecutor with an ActionBrokerClient-backed
    proposer. No cloud delete is ever called here; only propose_action.
    """
    logger.info("execute: proposing teardown via Action Broker")
    state["execution"] = None  # SKELETON: DecommissionExecutor.execute(plan)
    return state


def validate_node(state: dict[str, Any]) -> dict[str, Any]:
    """Step 5: re-scan and validate closure readiness."""
    logger.info("validate: re-scanning estate for residual resources")
    state["validation"] = None  # SKELETON: Validator.validate(plan, post_inventory)
    return state


def report_node(state: dict[str, Any]) -> dict[str, Any]:
    """Step 6: assemble and emit the final DecommissionReport."""
    logger.info("report: assembling closure-readiness report")
    state["report"] = None  # SKELETON: report.build_report(...)
    return state


def _has_deletions(state: dict[str, Any]) -> bool:
    """True if the plan contains at least one delete action (gates the HITL step)."""
    plan = state.get("plan")
    return bool(plan is not None and getattr(plan, "to_delete", 0) > 0)


# --------------------------------------------------------------------------- #
# Agent constructor
# --------------------------------------------------------------------------- #


def build_decommission_agent(settings: AopSettings, *, toolsets: list[Any] | None = None) -> Any:
    """Construct and return the Decommission ``LlmAgent``.

    A read-only discovery agent that proposes teardowns via the Action Broker.
    ``toolsets`` defaults to the decommission MCP allow-list + the Action Broker
    (built at deploy time, needs credentials); tests inject an explicit list to
    construct offline.
    """
    from google.adk.agents import LlmAgent

    if toolsets is None:
        toolsets = build_mcp_toolsets(
            DECOMMISSION_MCP_ENDPOINTS,
            region=settings.region,
            extra_custom_endpoints=[settings.action_broker_mcp_endpoint],
        )

    model = ModelFactory.from_settings(settings).get_model()
    logger.info("build_decommission_agent: model=%s tools=%d", settings.model_id, len(toolsets))

    return LlmAgent(
        name="decommission_agent",
        model=model,
        instruction=DECOMMISSION_SYSTEM_PROMPT,
        tools=toolsets,
    )
