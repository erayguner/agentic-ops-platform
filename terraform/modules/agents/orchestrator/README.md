# module/agents/orchestrator

Deploys the AOP Ops Orchestrator agent — the duty-manager that deduplicates
operational signals, correlates incidents, routes to specialists via A2A, and
owns the Slack incident conversation.

## What it provisions

- `sa-orchestrator` service account
- Vertex AI Reasoning Engine (with optional Memory Bank variant)
- IAM grants:
  - `roles/logging.viewer`, `roles/monitoring.viewer`, `roles/datastore.user`
  - Pub/Sub subscriber on `ops.signals`
  - Pub/Sub publisher on `ops.notifications`, `ops.audit`
- Optional Cloud Scheduler trigger

## Inputs

| Name                         | Required | Description                            |
| ---------------------------- | -------- | -------------------------------------- |
| `project_id`                 | yes      |                                        |
| `region`                     | no       | default `europe-west2`                 |
| `env`                        | yes      | `dev` / `staging` / `prod`             |
| `ops_signals_topic_id`       | yes      | subscriber binding                     |
| `ops_notifications_topic_id` | yes      | publisher binding                      |
| `ops_audit_topic_id`         | yes      | publisher binding (required for audit) |
| `deletion_policy_prevent`    | no       | `true` in prod                         |
| `enable_memory_bank`         | no       | creates a beta variant                 |
| `package_pickle_gcs_uri`     | no       | placeholder fails the base `check`     |
| `schedule`                   | no       | Cloud Scheduler config                 |
| `labels`                     | no       | extra labels                           |

## Outputs

`sa_email`, `sa_member`, `reasoning_engine_id`, `memory_bank_reasoning_engine_id`, `scheduler_job_id`.
