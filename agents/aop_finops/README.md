# FinOps Agent

## Purpose

Cost-intelligence specialist. Monitors spend anomalies, budget burn rate, idle/oversized resource waste, and rightsizing opportunities. Wraps the native Gemini Cloud Assist FinOps agent where available. Produces a structured `Finding v1`.

## MCP allow-list

| Endpoint                                | Status  | Purpose                                        |
| --------------------------------------- | ------- | ---------------------------------------------- |
| `bigquery.googleapis.com/mcp`           | GA      | Billing export queries (billing_dataset)       |
| `recommender.googleapis.com/mcp`        | GA      | Active rightsizing recommendations             |
| `geminicloudassist.googleapis.com/mcp`  | Preview | FinOps agent narrative (graceful fallback)     |
| `developerknowledge.googleapis.com/mcp` | GA      | Billing / Recommender API documentation lookup |
| Action Broker MCP (custom)              | —       | cost.shrink_idle_resource proposals            |

## Action classes this agent may propose

- `cost.shrink_idle_resource` — Tier 2 dev / Tier 3 prod
- `incident.escalate_to_human` — Tier 0 always

## Cost impact reporting

Every Finding must include cost impact in:

- Absolute GBP (or local billing currency).
- Percentage change vs. same period last month.
- Estimated monthly run-rate if anomaly continues.

## Deployment

Service account: `sa-finops@<project>.iam.gserviceaccount.com`
Deployed as `google_vertex_ai_reasoning_engine` on Agent Engine.
