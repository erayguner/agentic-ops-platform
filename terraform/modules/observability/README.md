# module/observability

Cloud Monitoring resources for the AOP: notification channels, alert policies, dashboards, log-based metrics, uptime checks, and SLOs.

## Resources created

- **Notification channel (Slack)** — native type with `auth_token_wo` + `auth_token_wo_version`. Token is write-only and never stored in Terraform state.
- **Notification channel (Pub/Sub)** — redundant delivery path for Critical alerts; independent of the Slack delivery service.
- **Alert policies (3)** — Agent down, Decision latency p95 > 60 s, Action rollback rate > 5%.
- **Log-based metrics (3)** — `aop_token_spend_total`, `aop_policy_denial_count`, `aop_action_rollback_count`.
- **Uptime checks (2)** — action-broker `/healthz`, slack-notifier `/healthz`.
- **SLO** — action-broker availability (99.5% / 30-day rolling).
- **Dashboard** — `AOP Platform Overview` with token spend, policy denials, rollback count, and agent request rate tiles.

## Slack token rotation

Increment `slack_auth_token_version` in `terraform.tfvars` and re-apply. Terraform will write the new token without storing it in state.

## Usage

```hcl
module "observability" {
  source = "../../modules/observability"

  project_id                 = "ops-agents-dev"
  env                        = "dev"
  slack_auth_token           = var.slack_auth_token    # from Secret Manager / CI
  slack_workspace_id         = var.slack_workspace_id
  ops_notifications_topic_id = module.eventing.ops_notifications_topic_id
  broker_url                 = module.action_broker.service_url
  notifier_url               = module.slack_notifier.service_url
}
```

## Inputs

| Name                       | Type               | Default        | Required |
| -------------------------- | ------------------ | -------------- | -------- |
| project_id                 | string             | —              | yes      |
| env                        | string             | —              | yes      |
| slack_auth_token           | string (sensitive) | placeholder    | yes      |
| slack_workspace_id         | string             | placeholder    | yes      |
| ops_notifications_topic_id | string             | —              | yes      |
| broker_url                 | string             | placeholder    | no       |
| notifier_url               | string             | placeholder    | no       |
| slack_channel_incidents    | string             | #ops-incidents | no       |

## Outputs

See `outputs.tf` for notification channel IDs, alert policy names, dashboard ID, and uptime check IDs.
