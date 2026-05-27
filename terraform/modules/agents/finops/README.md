# module/agents/finops

Deploys the AOP FinOps agent — cost/burn/waste specialist.

## Provisions

- `sa-finops` service account
- Vertex AI Reasoning Engine
- BigQuery binding strategy:
  - **preferred** (when `billing_export_bq_dataset_id` is set):
    - dataset-scoped `roles/bigquery.dataViewer` on the named billing dataset
    - project-scoped `roles/bigquery.jobUser` (needed to RUN queries)
  - **fallback** (when the dataset is empty):
    - project-scoped `roles/bigquery.dataViewer` — looser; the module's
      `check` block fails the plan if you try this in `env = "prod"`.
- `roles/recommender.viewer` (project)
- Pub/Sub publisher on `ops.findings`, `ops.notifications`, `ops.audit`
- Optional Cloud Scheduler trigger

## Inputs

| Name | Required | Notes |
|------|----------|-------|
| `project_id` | yes | |
| `env` | yes | |
| `ops_findings_topic_id` | yes | |
| `ops_notifications_topic_id` | yes | |
| `ops_audit_topic_id` | yes | |
| `billing_export_bq_dataset_id` | recommended | leave empty only in dev / sandbox |
| `billing_export_bq_project_id` | no | defaults to `project_id` |
| `deletion_policy_prevent` | no | `true` in prod |
| `schedule` | no | |
| `labels` | no | |

See [FRAMEWORK.md](../../../FRAMEWORK.md).
