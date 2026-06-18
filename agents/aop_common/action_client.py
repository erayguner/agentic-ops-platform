"""aop_common.action_client — typed client for the Action Broker MCP.

Agents NEVER execute writes directly. This client proposes actions to the
Action Broker via its MCP 'propose_action' tool. The Broker handles policy
evaluation, approval routing, and execution.

All methods are skeletons; no real MCP call is made in this scaffold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from aop_common.schemas import ActionRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProposalResult:
    """Result returned from a propose_action call."""

    action_id: str
    action_request: ActionRequest
    broker_response: dict[str, Any]


class ActionBrokerClient:
    """Typed, read-only client that calls the Action Broker MCP.

    This client proposes actions only — it never executes them.
    The Action Broker is the single execution choke point (DESIGN-REVIEW §3.2).

    Args:
        mcp_endpoint: Streamable HTTP URL for the Action Broker MCP server.
        agent_identity: SPIFFE URI or SA email of the calling agent.
            Included in the MCP call for audit attribution.
    """

    def __init__(self, mcp_endpoint: str, agent_identity: str) -> None:
        self._endpoint = mcp_endpoint
        self._agent_identity = agent_identity

    def propose_action(
        self,
        action_class: str,
        target: dict[str, str],
        params: dict[str, Any],
        rationale: str,
        proposed_tier: int,
        correlation_id: str,
        approval_window_until: str,
    ) -> ProposalResult:
        """Propose an action to the Action Broker for policy evaluation and approval.

        The Broker will:
        1. Validate the action class against the policy catalogue.
        2. Evaluate the autonomy tier (may upgrade proposed_tier on policy grounds).
        3. For Tier 2: auto-approve and execute within bounds.
        4. For Tier 3/4: route to Slack for human approval.
        5. Emit ActionRequest to ops.actions.requested.

        Args:
            action_class: Canonical action class string (see
                          `services/action-broker/policy/action_classes.yaml`).
                          E.g. "cloud_run.rollback_to_previous".
            target: Resource target dict (type, name, project, region).
            params: Action-class-specific parameters.
            rationale: Human-readable rationale for the proposed action.
            proposed_tier: Autonomy tier the agent proposes (0-4).
            correlation_id: Incident correlation id for audit linkage.
            approval_window_until: RFC3339 expiry timestamp for Tier-3 approvals.

        Returns:
            ProposalResult with the action_id and ActionRequest record.

        Raises:
            NotImplementedError: Skeleton — real MCP call not implemented.

        ADK 2.0 API — confirm MCP tool invocation pattern against adk.dev/2.0/ release notes
        """
        logger.info(
            "propose_action called: class=%s target=%s tier=%d correlation=%s",
            action_class,
            target,
            proposed_tier,
            correlation_id,
        )
        # SKELETON: In production, invoke the MCP tool via ADK 2.0 McpToolset:
        #   result = self._toolset.call_tool(
        #       "propose_action",
        #       {
        #           "action_class": action_class,
        #           "target": target,
        #           "params": params,
        #           "rationale": rationale,
        #           "proposed_tier": proposed_tier,
        #           "caller_identity": self._agent_identity,
        #           "correlation_id": correlation_id,
        #           "approval_window_until": approval_window_until,
        #       },
        #   )
        raise NotImplementedError(
            "ActionBrokerClient.propose_action is a skeleton. "
            "Wire the ADK 2.0 McpToolset call before connecting to the real Broker."
        )
