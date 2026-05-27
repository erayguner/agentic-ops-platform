# module/agents/_base

Shared base module for AOP agents. Provisions the resources that are identical
across every agent type:

- a dedicated service account (`sa-<agent_slug>`)
- the Vertex AI Reasoning Engine (GA spec; optional Memory Bank variant on beta)
- the audit-topic publisher binding (every agent must be able to emit to `ops.audit`)
- optional additional Pub/Sub publisher/subscriber bindings
- project-level IAM grants (predefined + custom roles, both least-privilege)
- an optional Cloud Scheduler trigger
- Terraform-native `check` blocks that fail the plan on common misconfigurations

The per-agent modules (`agents/orchestrator`, `agents/sre`, …) wrap this base
with their domain-specific IAM allow-list. Most consumers should not call
`_base` directly — use one of the agent wrappers or the top-level
`aop-platform` composition instead.

## Inputs

| Name | Required | Notes |
|------|----------|-------|
| `project_id` | yes | |
| `region` | yes | |
| `env` | yes | `dev` / `staging` / `prod` |
| `agent_slug` | yes | lowercase, becomes `sa-<slug>` |
| `agent_display_name` | yes | shown on Reasoning Engine |
| `agent_description` | yes | shown on Reasoning Engine and SA |
| `ops_audit_topic_id` | yes | publisher binding is non-negotiable |
| `project_iam_roles` | no | validated to refuse `owner`/`editor` |
| `custom_project_iam_role_ids` | no | full role IDs |
| `extra_pubsub_publish_topic_ids` | no | additional publisher topics |
| `extra_pubsub_subscribe_topic_ids` | no | subscriber topics |
| `schedule` | no | Cloud Scheduler config (cron + HTTPS target) |
| `enable_memory_bank` | no | creates a second Reasoning Engine on beta provider |
| `deletion_policy_prevent` | no | `true` in prod |
| `package_pickle_gcs_uri` | no | placeholder fails the `check` block when left default |
| `labels` | no | merged into the canonical AOP label set |

## Outputs

- `sa_email`, `sa_member`, `sa_name`
- `reasoning_engine_id`, `reasoning_engine_name`
- `memory_bank_reasoning_engine_id` (empty when disabled)
- `scheduler_job_id` (empty when no schedule)
- `labels`
