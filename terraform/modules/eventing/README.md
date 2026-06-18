# module/eventing

The Pub/Sub event spine and Eventarc bridge layer for the AOP.

## Resources created

- **7 Pub/Sub topics** — `ops.signals`, `ops.findings`, `ops.actions.requested`, `ops.actions.approved`, `ops.actions.executed`, `ops.notifications`, `ops.audit`.
- **7 DLQ topics** — one per main topic (e.g. `ops.signals.dlq`).
- **3 Avro schemas** — attached to `ops.signals`, `ops.notifications`, and `ops.audit`. Minimal but valid Avro records matching the Pydantic models in `agents/aop_common/schemas.py`.
- **BigQuery table** — `audit_events` (day-partitioned on timestamp) in the governance audit dataset.
- **BigQuery subscription** — `ops.audit.bq-sub` pushes audit records directly into the BQ table via `use_topic_schema = true`.
- **Eventarc trigger 1** — Cloud Audit Logs (IAM) → `ops.signals` (Pub/Sub destination).
- **Eventarc trigger 2** — `ops.notifications` topic → `slack-notifier` Cloud Run service.

## Usage

```hcl
module "eventing" {
  source = "../../modules/eventing"

  project_id          = "ops-agents-dev"
  env                 = "dev"
  audit_bq_dataset_id = module.governance.audit_bq_dataset_id
  slack_notifier_url  = module.slack_notifier.service_url
}
```

## Inputs

| Name                    | Type   | Default      | Required |
| ----------------------- | ------ | ------------ | -------- |
| project_id              | string | —            | yes      |
| env                     | string | —            | yes      |
| audit_bq_dataset_id     | string | —            | yes      |
| audit_bq_table_id       | string | audit_events | no       |
| slack_notifier_url      | string | placeholder  | no       |
| deletion_policy_prevent | bool   | false        | no       |
| region                  | string | europe-west2 | no       |

## Outputs

All topic IDs (resource IDs and names) are exported. See `outputs.tf`.
