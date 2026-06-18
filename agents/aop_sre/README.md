# SRE Agent

## Purpose

Reliability specialist. Investigates latency, error rate, saturation, SLO burn, deploy-related regressions, dependency outages, and capacity. Produces a structured `Finding v1` with typed recommendations.

## MCP allow-list

| Endpoint                                 | Status  | Purpose                                                    |
| ---------------------------------------- | ------- | ---------------------------------------------------------- |
| `logging.googleapis.com/mcp`             | GA      | Log queries for error / latency signals                    |
| `monitoring.googleapis.com/mcp`          | GA      | Metric anomaly detection                                   |
| `cloudtrace.googleapis.com/mcp`          | GA      | Request-path tracing                                       |
| `clouderrorreporting.googleapis.com/mcp` | GA      | Error cluster analysis                                     |
| `container.googleapis.com/mcp`           | GA      | GKE deployment and node health                             |
| `run.googleapis.com/mcp`                 | GA      | Cloud Run revision and health                              |
| `networkmanagement.googleapis.com/mcp`   | GA      | Network topology / connectivity                            |
| `geminicloudassist.googleapis.com/mcp`   | Preview | Cloud Assist Investigations (Premium-gated)                |
| `developerknowledge.googleapis.com/mcp`  | GA      | Official Google docs lookup for runtime config / debugging |
| Action Broker MCP (custom)               | —       | Action proposals only — no direct writes                   |

## Action classes this agent may propose

- `cloud_run.scale_within_range` — Tier 2 dev / Tier 2 prod
- `cloud_run.restart_revision` — Tier 2 dev / Tier 3 prod
- `cloud_run.rollback_to_previous` — Tier 2 dev / Tier 3 prod
- `gke.cordon_drain_node` — Tier 2 dev / Tier 3 prod
- `workflows.run` (\*-dryrun) — Tier 2 / Tier 2
- `incident.escalate_to_human` — Tier 0 always

## Deployment

Service account: `sa-sre@<project>.iam.gserviceaccount.com`
Deployed as `google_vertex_ai_reasoning_engine` on Agent Engine.
