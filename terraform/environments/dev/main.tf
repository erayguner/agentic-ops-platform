locals {
  env = "dev"
  # audit_bq_dataset_id is a fixed name; pass it directly to break the
  # governance→eventing→governance cycle.
  audit_bq_dataset_id = "audit_logs"
}

# ---------------------------------------------------------------------------
# Foundation — VPC, Artifact Registry, Essential Contacts, API enablement
# ---------------------------------------------------------------------------

module "foundation" {
  source = "../../modules/foundation"

  project_id               = var.project_id
  env                      = local.env
  region                   = var.region
  essential_contacts_email = var.essential_contacts_email
  org_id                   = var.org_id
  folder_id                = var.folder_id
}

# ---------------------------------------------------------------------------
# Eventing — Pub/Sub topics, schemas, DLQs, BQ audit table, Eventarc triggers
# audit_bq_dataset_id passed as a literal to avoid the cycle:
#   eventing → governance → eventing
# The Eventarc trigger for the notifier uses a placeholder URL; the actual
# URL is wired after the first apply once the notifier exists.
# ---------------------------------------------------------------------------

module "eventing" {
  source = "../../modules/eventing"

  project_id               = var.project_id
  env                      = local.env
  region                   = var.region
  audit_bq_dataset_id      = local.audit_bq_dataset_id
  enable_eventarc_triggers = false # no orchestrator Cloud Run ingest endpoint yet (see docs/deployment)
  # slack_notifier_url not passed here to avoid the cycle
  # eventing → slack_notifier → eventing (via Eventarc trigger destination).
  # The Eventarc trigger references the service name directly (not the URL)
  # so no runtime cycle exists; the variable default placeholder is used on
  # first apply and the trigger is updated on the second apply once the
  # notifier Cloud Run service exists.

  depends_on = [module.foundation]
}

# ---------------------------------------------------------------------------
# Governance — Model Armor, SCC, Org Policy, audit sink, Auditor role
# Depends on eventing for the SCC notification topic.
# ---------------------------------------------------------------------------

module "governance" {
  source = "../../modules/governance"

  project_id                    = var.project_id
  env                           = local.env
  region                        = var.region
  org_id                        = var.org_id
  folder_id                     = var.folder_id
  audit_bq_dataset_id           = local.audit_bq_dataset_id
  scc_notification_pubsub_topic = module.eventing.ops_signals_topic_id
  enable_org_policies           = false # no organization on the dev project
  enable_scc                    = false # SCC is organization-level
  enable_model_armor            = false # enable once there is agent traffic to screen

  depends_on = [module.foundation, module.eventing]
}

# ---------------------------------------------------------------------------
# Slack Notifier — deployed before observability (uptime check needs URL)
# ---------------------------------------------------------------------------

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
  deletion_protection              = false # dev: allow clean destroy
  seed_placeholder_secret_versions = true  # dev: deploy without real Slack tokens

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Action Broker
# ---------------------------------------------------------------------------

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
  min_instance_count             = 0     # dev: scale to zero
  deletion_protection            = false # dev: allow clean destroy

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Observability — alerts, dashboards, log-based metrics, SLOs, uptime checks
# ---------------------------------------------------------------------------

module "observability" {
  source = "../../modules/observability"

  project_id                 = var.project_id
  env                        = local.env
  region                     = var.region
  slack_auth_token           = var.slack_auth_token
  slack_auth_token_version   = var.slack_auth_token_version
  slack_workspace_id         = var.slack_workspace_id
  slack_channel_incidents    = var.slack_channel_incidents
  slack_channel_security     = var.slack_channel_security
  ops_notifications_topic_id = module.eventing.ops_notifications_topic_id
  broker_url                 = module.action_broker.service_url
  notifier_url               = module.slack_notifier.service_url

  depends_on = [module.slack_notifier, module.action_broker]
}

# ---------------------------------------------------------------------------
# Agent Runtime — reasoning engines + SAs + IAM
# ---------------------------------------------------------------------------

module "agent_runtime" {
  source = "../../modules/agent-runtime"

  project_id                 = var.project_id
  env                        = local.env
  region                     = var.region
  deletion_policy_prevent    = false # dev: allow destroy
  ops_signals_topic_id       = module.eventing.ops_signals_topic_id
  ops_findings_topic_id      = module.eventing.ops_findings_topic_id
  ops_notifications_topic_id = module.eventing.ops_notifications_topic_id
  ops_audit_topic_id         = module.eventing.ops_audit_topic_id
  # billing_export_bq_dataset_id left empty in dev → finops uses project-wide
  # bigquery.dataViewer. Set in prod to scope to the actual billing dataset.

  depends_on = [module.foundation, module.eventing]
}

# ---------------------------------------------------------------------------
# Cross-cutting IAM — agent SAs receive run.invoker on the action-broker
# Cloud Run service so the MCP `propose_action` call resolves.
#
# Done at the env root (not inside either module) to avoid a cycle between
# modules action-broker (creates the service) and agent-runtime (creates
# the agent SAs). The action_broker module accepts an `agent_sa_emails`
# variable for the same purpose, but with the resources composed at the
# root level we keep the per-SA grants visible in the env wiring.
# ---------------------------------------------------------------------------

locals {
  agent_sa_emails = {
    orchestrator = module.agent_runtime.sa_orchestrator_email
    sre          = module.agent_runtime.sa_sre_email
    devsecops    = module.agent_runtime.sa_devsecops_email
    platform     = module.agent_runtime.sa_platform_email
    finops       = module.agent_runtime.sa_finops_email
  }
}

resource "google_cloud_run_v2_service_iam_member" "agent_invoke_broker" {
  for_each = local.agent_sa_emails

  project  = var.project_id
  location = var.region
  name     = "action-broker" # service name from the action-broker module
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value}"

  depends_on = [module.action_broker, module.agent_runtime]
}
