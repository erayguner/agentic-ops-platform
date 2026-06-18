# Sandbox validation root

A self-contained Terraform root used to **validate the full deploy → verify →
destroy lifecycle** of the AOP platform on a standalone (no-organization) GCP
project. It is not a production environment; it is the harness behind
[`docs/deployment/`](../../../docs/deployment/README.md).

## What it deploys

`foundation` (APIs, VPC, Artifact Registry, Essential Contacts) → `governance`
(audit BigQuery dataset + `_AllLogs` sink + Auditor role) → `eventing` (Pub/Sub
spine, schemas, DLQs, BQ audit table) → `slack-notifier` + `action-broker`
(Cloud Run) → `observability` (dashboards, alerts, log metrics, SLO, uptime
checks) → a monthly Cloud Billing **budget** guardrail.

## What it intentionally gates off (and why)

| Gated                             | Why                                                      | Re-enable                                                    |
| --------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------ |
| `agent-runtime` reasoning engines | Preview API + placeholder pickle artifacts (stub agents) | package agents, then add the module                          |
| Org Policy, SCC                   | Organization-scoped; this project has no org             | set `enable_org_policies` / `enable_scc` + `org_id`          |
| Model Armor                       | No agent traffic to screen yet                           | `enable_model_armor = true` in `governance`                  |
| Eventarc triggers                 | Cloud Run destinations absent on a clean first apply     | `enable_eventarc_triggers = true` after services exist       |
| Native Slack notification channel | Verified against a live token at create                  | `enable_slack_notification_channel = true` with a real token |

## State backend

**Local state, on purpose** — so `terraform destroy` removes 100% of
provisioned cloud resources with no state-bucket/KMS residual. Production uses
the GCS backend created by [`terraform/bootstrap`](../../bootstrap/).

## Run

```bash
# Real values go in sandbox.auto.tfvars (gitignored); see terraform.tfvars for the shape.
terraform -chdir=terraform/environments/sandbox init
terraform -chdir=terraform/environments/sandbox apply -target=module.foundation   # creates Artifact Registry + enables APIs
# build + push the two images (see docs/deployment/GCLOUD-COMMANDS.md), then:
terraform -chdir=terraform/environments/sandbox apply
# ... verify ...
terraform -chdir=terraform/environments/sandbox destroy
```

See [`docs/deployment/`](../../../docs/deployment/README.md) for the full runbook,
required APIs, cost estimate, gcloud one-offs, and the deployment log.
