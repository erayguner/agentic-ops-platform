# AOP Deployment & Validation

How the Agentic Operations Platform is deployed to Google Cloud with Terraform,
validated, and cleanly destroyed. This directory is the audit trail for the
deploy/destroy lifecycle run on **`agentic-ops-platform`** (europe-west2).

## Contents

| Doc | What |
|-----|------|
| [`DEPLOYMENT-LOG.md`](./DEPLOYMENT-LOG.md) | Full chronicle: findings F1–F18, every apply/destroy pass, fixes, verification, teardown, residuals |
| [`REQUIRED-APIS.md`](./REQUIRED-APIS.md) | Every required GCP API and where it is enabled in Terraform |
| [`COST-ESTIMATE.md`](./COST-ESTIMATE.md) | Monthly cost by scenario, unit prices, free tier, sources |
| [`GCLOUD-COMMANDS.md`](./GCLOUD-COMMANDS.md) | Every non-Terraform/gcloud step: reason, command, expected result, reversal |
| [`AGENT-DEPLOY.md`](./AGENT-DEPLOY.md) | One-step-away procedure to deploy the agent tier (Agent Engine) once the agents are built out |
| [`RETROSPECTIVE.md`](./RETROSPECTIVE.md) | Lessons learned / retro for the whole deploy-validation & hardening effort (themes, decisions, metrics, action items) |

## What gets deployed

`foundation` (APIs, VPC, Artifact Registry, Essential Contacts) → `governance`
(audit BigQuery dataset + `_AllLogs` log sink + Auditor role) → `eventing`
(Pub/Sub topics, schemas, DLQs, BQ audit table) → `slack-notifier` +
`action-broker` (Cloud Run, real images) → `observability` (dashboards, alerts,
log-based metrics, uptime checks) → Cloud Billing **budget**. **103 resources**,
all Terraform-managed.

### Intentionally gated (see DEPLOYMENT-LOG for the why + the flag to re-enable)

Vertex AI reasoning engines (Preview + stub agents) · Org Policy + SCC (org-only;
this project has no organization) · Model Armor (no agent traffic yet) · Eventarc
triggers (Cloud Run destinations absent on first apply) · ops.audit→BigQuery
subscription (AVRO↔BQ schema mismatch) · Agent-Engine alert policies + the
availability SLO (need running agents / a reworked SLI).

## Prerequisites (external — not created/destroyed by Terraform)

- GCP project + **billing enabled** (this project: billing on, currency GBP).
- `gcloud` authenticated with ADC: `gcloud auth application-default login`.
- Terraform ≥ 1.11 (validated on 1.14), `gcloud`, and Docker-less Cloud Build.
- `serviceusage.googleapis.com` enabled (default on new projects).
- An organization is **optional** — without it, Org Policy/SCC stay gated.

## Deploy (validation root, local state)

Real values go in `terraform/environments/sandbox/sandbox.auto.tfvars`
(gitignored; see `terraform.tfvars` for the shape).

```bash
cd terraform/environments/sandbox
terraform init

# 1) Foundation first — creates Artifact Registry + enables APIs.
terraform apply -target=module.foundation

# 2) Build + push the two images (Terraform can't build containers).
AR="europe-west2-docker.pkg.dev/<project>/aop-containers"
gcloud builds submit ../../../services/slack-notifier --config=../../../services/cloudbuild.yaml \
  --substitutions=_IMAGE="$AR/slack-notifier:latest" --region=europe-west2
gcloud builds submit ../../../services/action-broker --config=../../../services/cloudbuild.yaml \
  --substitutions=_IMAGE="$AR/action-broker:latest" --region=europe-west2

# 3) Full apply.
terraform apply
```

## Verify

```bash
terraform plan -detailed-exitcode      # exit 0 = state matches reality
gcloud run services list --region=europe-west2   # both Ready=True
```

## Destroy (clean teardown)

```bash
terraform destroy

# Remove the two non-Terraform side-effects (see GCLOUD-COMMANDS.md):
gcloud storage rm --recursive gs://<project>_cloudbuild --quiet
gcloud compute firewall-rules delete default-allow-icmp default-allow-internal \
  default-allow-rdp default-allow-ssh --quiet
gcloud compute networks delete default --quiet
```

After this, **no Terraform-managed resources and no deploy-created
infrastructure remain.** Enabled APIs and Google-managed service agents persist
(documented, harmless, no cost). The project, billing account, and any
pre-existing budgets are left untouched.

## Production note

The sandbox root uses **local state** so destroy leaves zero residual. The
production path (`environments/dev|prod`) uses the **GCS backend** created by
`terraform/bootstrap` (state bucket + CMEK KMS + WIF + runner SAs). Bootstrap is
a one-time, documented prerequisite layer; its KMS keyring/key **cannot be
deleted in GCP** (only key versions destroyed) and the bucket is
`force_destroy = false`, so applying bootstrap leaves permanent residual by
design — which is why the teardown-clean validation uses local state instead.

## Module changes that make all this repeatable

Backward-compatible flags/fixes added to the shared modules (dev/prod still
`validate`): foundation (API ordering + `cloudbuild`), governance
(`enable_org_policies`/`enable_scc`/`enable_model_armor`/`delete_contents_on_destroy`,
single Essential Contact), eventing (`enable_eventarc_triggers`/
`enable_bq_audit_subscription` + Pub/Sub→BQ IAM), action-broker/slack-notifier
(`deletion_protection`, seeded placeholder secret versions), observability
(`enable_slack_notification_channel`/`enable_agent_engine_alerts`/`enable_slo`,
metric/uptime/alert-filter + destroy-ordering fixes). See `DEPLOYMENT-LOG.md`.
