locals {
  env = "prod"
  # audit_bq_dataset_id is a fixed name; pass it directly to break the cycle.
  audit_bq_dataset_id = "audit_logs"
}

# ---------------------------------------------------------------------------
# Foundation
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
# Eventing — audit_bq_dataset_id literal avoids governance→eventing cycle
# ---------------------------------------------------------------------------

module "eventing" {
  source = "../../modules/eventing"

  project_id              = var.project_id
  env                     = local.env
  region                  = var.region
  audit_bq_dataset_id     = local.audit_bq_dataset_id
  deletion_policy_prevent = true # prod: protect ops.audit topic from accidental destroy

  depends_on = [module.foundation]
}

# ---------------------------------------------------------------------------
# Governance — prod adds enforced Org Policy bindings
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

  depends_on = [module.foundation, module.eventing]
}

# ---------------------------------------------------------------------------
# Slack Notifier — prod channel names differ
# ---------------------------------------------------------------------------

module "slack_notifier" {
  source = "../../modules/slack-notifier"

  project_id                    = var.project_id
  env                           = local.env
  region                        = var.region
  container_image               = var.container_image_slack_notifier
  ops_notifications_topic_id    = module.eventing.ops_notifications_topic_id
  ops_actions_approved_topic_id = module.eventing.ops_actions_approved_topic_id
  slack_channel_incidents       = var.slack_channel_incidents
  slack_channel_security        = var.slack_channel_security
  slack_channel_finops          = var.slack_channel_finops
  slack_channel_platform        = var.slack_channel_platform
  min_instance_count            = 1 # prod: always warm

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Action Broker — prod keeps at least one instance warm
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
  min_instance_count             = 1 # prod: keep warm

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Observability
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
# Agent Runtime — prod: deletion_policy_prevent = true
# ---------------------------------------------------------------------------

module "agent_runtime" {
  source = "../../modules/agent-runtime"

  project_id                 = var.project_id
  env                        = local.env
  region                     = var.region
  deletion_policy_prevent    = true # prod: PREVENT deletion of reasoning engines
  ops_signals_topic_id       = module.eventing.ops_signals_topic_id
  ops_findings_topic_id      = module.eventing.ops_findings_topic_id
  ops_notifications_topic_id = module.eventing.ops_notifications_topic_id
  ops_audit_topic_id         = module.eventing.ops_audit_topic_id
  # Dataset-scoped FinOps BigQuery binding — set to the actual billing
  # export dataset to remove the wider project-wide dataViewer fallback.
  billing_export_bq_dataset_id = var.billing_export_bq_dataset_id
  billing_export_bq_project_id = var.billing_export_bq_project_id

  depends_on = [module.foundation, module.eventing]
}

# ---------------------------------------------------------------------------
# Cross-cutting IAM — agent SAs receive run.invoker on the action-broker
# Cloud Run service. Done at env-root level to avoid a cycle between
# modules action-broker and agent-runtime (each would otherwise need to
# know the other's outputs at plan-time).
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
