# Ops Orchestrator Agent

## Purpose

Duty-manager hub. Receives every operational signal, deduplicates, correlates, classifies, and routes to the appropriate specialist agent via ADK `sub_agents` (A2A when specialists are externalised). Owns the Slack incident conversation from open to close. The only agent that initiates HITL approval flows.

## MCP allow-list

| Endpoint                                  | Purpose                            |
| ----------------------------------------- | ---------------------------------- |
| `logging.googleapis.com/mcp`              | Correlation log queries            |
| `pubsub.googleapis.com/mcp`               | Signal and notification topics     |
| `cloudresourcemanager.googleapis.com/mcp` | Project / resource context         |
| Action Broker MCP (custom)                | Relay ActionApproval decisions     |
| Org Context MCP (custom)                  | Owner, team, change-freeze lookups |

## Action classes the orchestrator may propose

None. The orchestrator does not produce Findings or Recommendations.
It relays Tier-3/4 ActionApproval decisions received from humans via Slack.

## Realisation (ADK 2.3)

The orchestrator is an `LlmAgent` COORDINATOR whose `sub_agents` are the four
specialists (sre / devsecops / platform / finops); it routes a triaged signal to
the right one. ADK 2.3 has no graph `WorkflowAgent`, so the deterministic,
non-LLM steps below are owned by the eventing + Action Broker layers (the broker
is the policy-gated, HITL-capable executor) and live as helper functions in
`agent.py`:

```
receive_signal → dedup → [drop if dup] → classify → route
    → wait_for_finding → render_notification
    → [request_approval (HITL)] → close
```

The HITL gate activates only when a specialist Finding carries a Tier 3 or Tier 4 recommendation.

## Deployment

Deploys as a `google_vertex_ai_reasoning_engine` ("Deployment") on Agent Engine.
Service account: `sa-orchestrator@<project>.iam.gserviceaccount.com`.

## Environment variables (prefix `AOP_`)

See `aop_common.config.AopSettings` for the full list.
