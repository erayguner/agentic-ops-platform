# module/aop-platform

The top-level composition for the Agentic Operations Platform. Wraps every
component module and exposes a single declarative interface so a downstream
repo can stand up a working platform with one `module { source = ... }` block.

## Architecture

```text
                        ┌────────────────────────────┐
                        │     aop-platform (this)    │
                        └──────────────┬─────────────┘
                                       │
   ┌────────────┬────────────┬─────────┴─────────┬───────────────┐
   ▼            ▼            ▼                   ▼               ▼
foundation  eventing    governance         observability     action-broker
   │            │            │                   │               │
   │            │            │                   │               │
   ▼            ▼            ▼                   ▼               ▼
   …          Pub/Sub      Model        dashboards/alerts    Cloud Run
            schemas,DLQ    Armor,SCC                          + per-class SAs
                              + audit
                            BQ sink

                              ┌────────────────── agents/ ────────────────────┐
                              │ orchestrator  sre  devsecops  platform  finops│
                              └───────────────────────────────────────────────┘
```

Each box is its own module under `terraform/modules/*`. Every agent is
opt-in via the `enabled_agents` map.

## Quick start

```hcl
module "aop" {
  source = "github.com/erayguner/agentic-ops-platform//terraform/modules/aop-platform?ref=v0.5.1" # x-release-please-version

  project_id = "ops-agents-dev"
  env        = "dev"
  region     = "europe-west2"

  # Pick the agents you need. Drop a key to skip the agent entirely.
  enabled_agents = {
    sre      = {}
    finops   = { schedule = { cron = "0 6 * * *", target_uri = "https://finops-fan-out.example.com/run" } }
    devsecops = {}
  }

  # Slack token is injected by CI — never commit it.
  slack_auth_token   = var.slack_auth_token
  slack_workspace_id = var.slack_workspace_id

  essential_contacts_email = "platform-owner@example.com"
}
```

## What's enabled by default

| Component | Default | Override flag |
|-----------|---------|---------------|
| Foundation (VPC, AR, Essential Contacts) | on | `enable_foundation` |
| Eventing (Pub/Sub, DLQs, BQ audit) | on | `enable_eventing` |
| Governance (Model Armor, SCC, OrgPolicy) | on | `enable_governance` |
| Observability (dashboards, alerts, SLOs) | on | `enable_observability` |
| Action Broker (Cloud Run) | on | `enable_action_broker` |
| Slack Notifier (Cloud Run) | on | `enable_slack_notifier` |
| All 5 agents | on | `enabled_agents` map |

## Plan-time invariants

The module surfaces several `check` blocks that abort the plan when the
configuration is unsafe — for example:

- `env = prod` MUST set `deletion_policy_prevent = true`
- `env = prod` MUST keep `min_instance_count_broker >= 1`
- agents can only be enabled when `enable_eventing = true`
- FinOps in prod MUST set `finops_billing_export_bq_dataset_id`

These are diagnostic checks (not validation errors) — your plan output
shows the assertion failure but Terraform still completes the plan. CI
treats any failing check as a build failure.

## Outputs

| Output | Notes |
|--------|-------|
| `topic_ids` | map of canonical Pub/Sub topic IDs |
| `agent_sa_emails` | map of agent slug → SA email |
| `agent_reasoning_engine_ids` | map of agent slug → engine ID |
| `agent_scheduler_job_ids` | map of agent slug → Cloud Scheduler job ID |
| `action_broker_url`, `slack_notifier_url` | Cloud Run URLs |
| `action_class_sa_emails` | per-action-class impersonation SAs |
| `auditor_role_id` | custom IAM role for compliance reviewers |
| `audit_bq_dataset_id` | dataset holding the audit log export |

See `outputs.tf` for the exhaustive list.

## Adopting from another repo

The full consumer pattern (separate state, WIF, pre-flight, release-please) is
documented in [`terraform/FRAMEWORK.md`](../../FRAMEWORK.md).
