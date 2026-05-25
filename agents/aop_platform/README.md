# Platform Engineering Agent

## Purpose

Drift and deployment-health specialist. Detects configuration drift versus declared IaC state, assesses deployment health, checks resource hygiene, and validates network/compliance posture. Produces a structured `Finding v1`.

## MCP allow-list

| Endpoint | Status | Purpose |
|---|---|---|
| `cloudasset.googleapis.com/mcp` | Preview | Resource inventory vs. expected state |
| `cloudresourcemanager.googleapis.com/mcp` | GA | Project/folder config and IAM drift |
| `container.googleapis.com/mcp` | GA | GKE cluster/workload health |
| `run.googleapis.com/mcp` | GA | Cloud Run service health and config |
| `compute.googleapis.com/mcp` | GA | Network config drift (VPC, firewall) |
| Action Broker MCP (custom) | — | terraform.plan and workflows.run proposals |

## Action classes this agent may propose

- `terraform.plan` — Tier 2 / Tier 2 (read-only; never `terraform.apply` without approval)
- `workflows.run` (*-dryrun) — Tier 2 / Tier 2
- `workflows.run` (production) — Tier 3 / Tier 3
- `incident.escalate_to_human` — Tier 0 always

## Deployment

Service account: `sa-platform@<project>.iam.gserviceaccount.com`
Deployed as `google_vertex_ai_reasoning_engine` on Agent Engine.
