# =============================================================================
# AOP — Sandbox validation root
# =============================================================================
# Purpose: prove the AOP platform deploys end-to-end from Terraform and tears
# down cleanly via `terraform destroy`, on a standalone (no-org) GCP project.
#
# Deliberate differences from environments/dev (full rationale in
# docs/deployment/DEPLOYMENT-LOG.md and docs/deployment/README.md):
#
#   * LOCAL state (see versions.tf) so destroy leaves zero residual.
#   * agent-runtime (Vertex AI reasoning engines) is NOT instantiated — it is a
#     Preview API loading placeholder pickle artifacts (stub agents); deploying
#     it cannot succeed cleanly and is out of scope for the lifecycle test.
#   * Module ordering is foundation -> governance -> eventing. dev orders
#     eventing before governance, but eventing's BQ audit *table* lives in the
#     dataset governance creates; that only works because governance no longer
#     depends on eventing once SCC is gated off (no scc_notification topic
#     needed), which removes the original eventing<->governance cycle.
#   * Org Policy + SCC gated off (no organization on this project).
#   * Model Armor gated off (no agent traffic to screen in this cycle).
#   * Eventarc triggers gated off (Cloud Run destinations absent on first apply).
#   * Cloud Run deletion_protection=false + seeded placeholder Slack secret
#     versions, so the services deploy and destroy without out-of-band inputs.
# =============================================================================

locals {
  env                 = "dev" # module env validation accepts dev|staging|prod
  audit_bq_dataset_id = "audit_logs"
}

# -----------------------------------------------------------------------------
# Foundation — enables ALL platform APIs (google_project_service), VPC, subnet,
# firewalls, Artifact Registry, Essential Contacts.
# -----------------------------------------------------------------------------
module "foundation" {
  source = "../../modules/foundation"

  project_id               = var.project_id
  env                      = local.env
  region                   = var.region
  essential_contacts_email = var.essential_contacts_email
  org_id                   = var.org_id
  folder_id                = var.folder_id
}

# -----------------------------------------------------------------------------
# Governance — audit BigQuery dataset + _AllLogs sink + Auditor custom role.
# Org Policy / SCC / Model Armor gated off for this no-org validation deploy.
# Runs BEFORE eventing because eventing's audit table lives in this dataset.
# -----------------------------------------------------------------------------
module "governance" {
  source = "../../modules/governance"

  project_id          = var.project_id
  env                 = local.env
  region              = var.region
  org_id              = var.org_id
  folder_id           = var.folder_id
  audit_bq_dataset_id = local.audit_bq_dataset_id

  enable_org_policies        = false # standalone project has no organization
  enable_scc                 = false # SCC (all tiers) is organization-level only
  enable_model_armor         = false # no agent traffic to screen this cycle
  deletion_policy_prevent    = false # allow destroy
  delete_contents_on_destroy = true  # drop sink-created tables on destroy

  depends_on = [module.foundation]
}

# -----------------------------------------------------------------------------
# Eventing — Pub/Sub spine (topics, schemas, DLQs), BQ audit table + BQ
# subscription. Eventarc triggers gated off (no Cloud Run destinations yet).
# -----------------------------------------------------------------------------
module "eventing" {
  source = "../../modules/eventing"

  project_id                   = var.project_id
  env                          = local.env
  region                       = var.region
  audit_bq_dataset_id          = local.audit_bq_dataset_id
  enable_eventarc_triggers     = false
  enable_bq_audit_subscription = true # F13 fixed: ops.audit AVRO ↔ audit_events BQ schema reconciled

  depends_on = [module.foundation, module.governance]
}

# -----------------------------------------------------------------------------
# Slack notifier — Cloud Run + secrets (placeholder versions seeded so the
# revision can deploy without out-of-band Slack tokens).
# -----------------------------------------------------------------------------
module "slack_notifier" {
  source = "../../modules/slack-notifier"

  project_id                       = var.project_id
  env                              = local.env
  region                           = var.region
  container_image                  = var.container_image_slack_notifier
  ops_notifications_topic_id       = module.eventing.ops_notifications_topic_id
  ops_actions_approved_topic_id    = module.eventing.ops_actions_approved_topic_id
  slack_channel_incidents          = var.slack_channel_incidents
  slack_channel_security           = var.slack_channel_security
  slack_channel_finops             = var.slack_channel_finops
  slack_channel_platform           = var.slack_channel_platform
  deletion_protection              = false
  seed_placeholder_secret_versions = true

  depends_on = [module.eventing]
}

# -----------------------------------------------------------------------------
# Action broker — Cloud Run + per-action-class SAs + least-privilege IAM.
# -----------------------------------------------------------------------------
module "action_broker" {
  source = "../../modules/action-broker"

  project_id                     = var.project_id
  env                            = local.env
  region                         = var.region
  container_image                = var.container_image_action_broker
  ops_actions_approved_topic_id  = module.eventing.ops_actions_approved_topic_id
  ops_actions_requested_topic_id = module.eventing.ops_actions_requested_topic_id
  ops_actions_executed_topic_id  = module.eventing.ops_actions_executed_topic_id
  ops_audit_topic_id             = module.eventing.ops_audit_topic_id
  min_instance_count             = 0 # scale to zero
  deletion_protection            = false

  depends_on = [module.eventing]
}

# -----------------------------------------------------------------------------
# Observability — dashboards, alerts, log-based metrics, SLOs, uptime checks.
# Native Slack notification channel gated off (no live token); alerts deliver
# via the Pub/Sub channel.
# -----------------------------------------------------------------------------
module "observability" {
  source = "../../modules/observability"

  project_id                        = var.project_id
  env                               = local.env
  region                            = var.region
  ops_notifications_topic_id        = module.eventing.ops_notifications_topic_id
  broker_url                        = module.action_broker.service_url
  notifier_url                      = module.slack_notifier.service_url
  slack_channel_incidents           = var.slack_channel_incidents
  slack_channel_security            = var.slack_channel_security
  enable_slack_notification_channel = false
  enable_agent_engine_alerts        = false # no reasoning engines deployed (see DEPLOYMENT-LOG F14)
  enable_slo                        = false # F15: SLI reworked to valid request-based, but an SLO needs existing metric data; a fresh never-invoked (internal) service has none → create as a 2nd-day apply

  depends_on = [module.slack_notifier, module.action_broker]
}

# -----------------------------------------------------------------------------
# Cost guardrail — monthly billing budget with 50/90/100% alerts.
# The budget lives at the billing-account scope; the Cloud Billing Budget API
# is enabled here (foundation only enables project-runtime APIs).
# -----------------------------------------------------------------------------
resource "google_project_service" "billingbudgets" {
  project            = var.project_id
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
}

resource "google_billing_budget" "sandbox" {
  billing_account = var.billing_account_id
  display_name    = "AOP sandbox budget ${var.budget_amount_usd}/mo"

  budget_filter {
    projects = ["projects/${var.project_number}"]
  }

  amount {
    specified_amount {
      # currency_code intentionally omitted: the budget inherits the billing
      # account's currency. The API rejects a mismatch (this account is GBP),
      # so hardcoding USD returns 400 "invalid argument".
      units = tostring(var.budget_amount_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  depends_on = [google_project_service.billingbudgets]
}
