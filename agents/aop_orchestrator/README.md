# Ops Orchestrator Agent

## Purpose

Duty-manager hub. Receives every operational signal, deduplicates, correlates, classifies, and routes to the appropriate specialist agent via A2A. Owns the Slack incident conversation from open to close. The only agent that initiates HITL approval flows.

## MCP allow-list

| Endpoint | Purpose |
|---|---|
| `logging.googleapis.com/mcp` | Correlation log queries |
| `pubsub.googleapis.com/mcp` | Signal and notification topics |
| `cloudresourcemanager.googleapis.com/mcp` | Project / resource context |
| Action Broker MCP (custom) | Relay ActionApproval decisions |
| Org Context MCP (custom) | Owner, team, change-freeze lookups |

## Action classes the orchestrator may propose

None. The orchestrator does not produce Findings or Recommendations.
It relays Tier-3/4 ActionApproval decisions received from humans via Slack.

## ADK 2.0 Workflow Runtime graph

```
receive_signal → dedup → [drop if dup] → classify → route
    → wait_for_finding → render_notification
    → [request_approval (HITL)] → close
```

HITL node activates only when a specialist Finding contains a Tier 3 or Tier 4 recommendation.

## Deployment

Deploys as a `google_vertex_ai_reasoning_engine` ("Deployment") on Agent Engine.
Service account: `sa-orchestrator@<project>.iam.gserviceaccount.com`.

## Environment variables (prefix `AOP_`)

See `aop_common.config.AopSettings` for the full list.
