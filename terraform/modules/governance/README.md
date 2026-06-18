# module/governance

Establishes the policy, security-control, and audit-routing layer for the AOP:

- **Model Armor floor setting** — `INSPECT_AND_BLOCK` with prompt-injection, sensitive-data, malicious-URI, and RAI filters. Applied at project scope; see the `google_model_armor_floorsetting` resource.
- **Model Armor template** — `aop-default-v1` starter template for per-request screening.
- **SCC v2** — project-scoped source, notification config (routes Critical/High findings to `ops.signals`), and BigQuery export.
- **Org Policy** — `iam.disableServiceAccountKeyCreation` and `gcp.resourceLocations` at project scope; folder/org variants are included as commented examples.
- **Audit log sink** — all project logs routed to a BigQuery dataset with partitioned tables.
- **Custom IAM role** — `aopAuditor` for compliance-review access.

## Notes

- Folder/org-scoped Org Policy and SCC notification variants are provided as commented `resource` blocks. Enable them by uncommenting and setting `org_id` / `folder_id`.
- The Model Armor floor setting integration with `GOOGLE_MCP_SERVER` is applied through the `floor_setting_enforcement = "ENABLED"` mode which activates INSPECT_AND_BLOCK for all integrated services.

## Usage

```hcl
module "governance" {
  source = "../../modules/governance"

  project_id                    = "ops-agents-dev"
  env                           = "dev"
  scc_notification_pubsub_topic = module.eventing.ops_signals_topic_id
}
```

## Inputs

| Name                          | Type   | Default    | Required |
| ----------------------------- | ------ | ---------- | -------- |
| project_id                    | string | —          | yes      |
| env                           | string | —          | yes      |
| scc_notification_pubsub_topic | string | —          | yes      |
| org_id                        | string | ""         | no       |
| folder_id                     | string | ""         | no       |
| audit_bq_dataset_id           | string | audit_logs | no       |
| model_armor_location          | string | global     | no       |

## Outputs

| Name                           | Description             |
| ------------------------------ | ----------------------- |
| audit_bq_dataset_id            | BQ dataset ID           |
| audit_log_sink_writer_identity | Log sink SA             |
| model_armor_template_id        | Model Armor template ID |
| scc_source_id                  | SCC source name         |
| auditor_role_id                | Custom Auditor role ID  |
