"""aop_common.policy_client — read-only client for the Org Context MCP.

The Org Context MCP server provides estate-specific lookups that no managed
Google MCP server exposes: project → owner mapping, service → team mapping,
environment classification, change-freeze calendar.

This client is read-only. It never proposes or executes actions.
The Org Context MCP server itself is stubbed in services/org-context/.

ADK 2.0 API — confirm McpToolset tool-call pattern against adk.dev/2.0/ release notes
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class OrgContextClient:
    """Read-only client for the Org Context MCP server.

    Args:
        mcp_endpoint: Streamable HTTP URL for the Org Context MCP server.
    """

    def __init__(self, mcp_endpoint: str) -> None:
        self._endpoint = mcp_endpoint

    def owner_of(self, project: str) -> str:
        """Return the human owner / team email for a GCP project.

        Raises:
            NotImplementedError: Skeleton.
        """
        raise NotImplementedError(
            "OrgContextClient.owner_of is a skeleton. Wire the Org Context MCP server before use."
        )

    def team_for(self, service: str) -> str:
        """Return the team responsible for a named service.

        Raises:
            NotImplementedError: Skeleton.
        """
        raise NotImplementedError("OrgContextClient.team_for is a skeleton.")

    def is_change_freeze(self, at: str, env: str) -> bool:
        """Return True if there is a change freeze at the given RFC3339 timestamp.

        Args:
            at: RFC3339 timestamp to check.
            env: Environment name ('dev' or 'prod').

        Raises:
            NotImplementedError: Skeleton.
        """
        raise NotImplementedError("OrgContextClient.is_change_freeze is a skeleton.")

    def service_criticality(self, service: str) -> str:
        """Return the criticality tier for a service: critical, high, medium, low.

        Raises:
            NotImplementedError: Skeleton.
        """
        raise NotImplementedError("OrgContextClient.service_criticality is a skeleton.")
