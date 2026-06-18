# Decommission Agent

## Purpose

Project-closure specialist. Prepares a target project for safe closure by
identifying, planning, executing, validating, and reporting on the full
decommissioning of its resources — leaving **no dormant, orphaned, unused,
billable, or unmanaged resource behind**, while retaining everything the
exemption policy protects (audit logs, billing exports, compliance records,
backups, break-glass identities, legally-held data).

It is a **campaign agent**: a multi-stage lifecycle, not a single signal→finding
pass. The real engine is pure Python and fully unit-tested; the ADK
`WorkflowAgent` graph in `agent.py` drives it.

```text
discover → inventory → plan → [approval gate] → execute → validate → report
```

## Decision/execution separation (the safety backbone)

The agent **never deletes anything directly** and holds **no write/delete IAM**.
Every teardown is a `propose_action` to the **Action Broker** — the single
execution choke point — which policy-gates it, routes prod destroys to human
approval, and runs the actual destroy only when `LIVE_MODE=true`. There is no
cloud-mutation call anywhere in this package; that is structural, not
conventional.

Four independent gates sit in front of any real deletion:

1. **Plan** — the dry-run plan shows exactly what would be deleted/retained/skipped.
2. **Execute dry-run** — the executor can rehearse proposals without calling the Broker.
3. **Approval tier** — the Broker routes Tier-3/4 destroys to human approval (prod = ≥2 approvers).
4. **`LIVE_MODE`** — the Broker's executors stay inert until explicitly enabled.

## Modules

| Module          | Responsibility                                                              |
| --------------- | --------------------------------------------------------------------------- |
| `inventory.py`  | Discover + reconcile (terraform/unmanaged/drifted/ghost) + classify         |
| `exemptions.py` | Policy-driven retention; **fails safe by halting** on a bad policy          |
| `planner.py`    | Dry-run plan, transitive retention, dependency-ordered deletion stages      |
| `executor.py`   | Staged, idempotent, resumable teardown via the Action Broker (propose-only) |
| `validation.py` | Post-decommission re-scan + closure-readiness assurance                     |
| `report.py`     | Final report + Markdown render + secret/PII redaction                       |
| `campaign.py`   | End-to-end lifecycle + per-phase audit emission                             |
| `agent.py`      | ADK 2.0 WorkflowAgent skeleton (graph nodes drive the campaign)             |

## MCP allow-list (read-only)

| Endpoint                        | Status  | Purpose                                                              |
| ------------------------------- | ------- | -------------------------------------------------------------------- |
| `cloudasset.googleapis.com/mcp` | Preview | Live estate inventory (Asset Inventory)                              |
| `monitoring.googleapis.com/mcp` | GA      | Activity + utilisation signals                                       |
| `logging.googleapis.com/mcp`    | GA      | Last-activity / access evidence                                      |
| Action Broker MCP (custom)      | —       | `terraform.destroy_target`, `decommission.delete_resource` proposals |

Resource Manager MCP is excluded fleet-wide (overlaps Asset Inventory — see
`docs/deployment/MCP-SERVERS.md`); project metadata reads are bounded by the
SA's `resourcemanager.projectViewer` role. Recommender MCP is deferred
(Preview), matching FinOps — `recommender.viewer` is granted for when it lands.

## Action classes this agent may propose

- `terraform.destroy_target` — Tier 3 (dev 1 approver / prod 2). Irreversible.
- `decommission.delete_resource` — Tier 3 (dev 1 approver / prod 2). Irreversible.
- `incident.escalate_to_human` — Tier 0 always.

## Exemptions

Retention is policy-driven. See [`exemptions.example.yaml`](./exemptions.example.yaml).
Rules match by resource id, type, name, service, environment, owner, criticality,
label, or Resource Manager tag; **every rule requires a `reason`** that appears in
the report. A missing, malformed, or match-everything policy **halts the
campaign** — the inverse of the Broker's fail-closed direction, because for a
destructive tool "protect nothing and proceed" is the catastrophic failure.

## Deployment

Service account: `sa-decommission@<project>.iam.gserviceaccount.com` (read-only;
created by `terraform/modules/agents/decommission`). Deployed as a
`google_vertex_ai_reasoning_engine` on Agent Engine; typically run on a Cloud
Scheduler cadence as a closure sweep.
