locals {
  audit_bq_dataset_id = "audit_logs"

  default_image_broker = (
    var.container_image_action_broker != ""
    ? var.container_image_action_broker
    : "${var.region}-docker.pkg.dev/${var.project_id}/aop-containers/action-broker:latest"
  )
  default_image_notifier = (
    var.container_image_slack_notifier != ""
    ? var.container_image_slack_notifier
    : "${var.region}-docker.pkg.dev/${var.project_id}/aop-containers/slack-notifier:latest"
  )

  # Resolve which agents are actually enabled (`enabled = false` skips).
  active_agent_keys = {
    for k, v in var.enabled_agents :
    k => v
    if coalesce(try(v.enabled, true), true)
  }

  agent_enabled = {
    orchestrator = contains(keys(local.active_agent_keys), "orchestrator")
    sre          = contains(keys(local.active_agent_keys), "sre")
    devsecops    = contains(keys(local.active_agent_keys), "devsecops")
    platform     = contains(keys(local.active_agent_keys), "platform")
    finops       = contains(keys(local.active_agent_keys), "finops")
  }
}

# ---------------------------------------------------------------------------
# Plan-time invariants — fail fast on conflicting flag combinations.
# ---------------------------------------------------------------------------

check "prod_requires_prevent_deletion" {
  assert {
    condition     = var.env != "prod" || var.deletion_policy_prevent
    error_message = "env = prod requires deletion_policy_prevent = true."
  }
}

check "prod_requires_broker_warm_pool" {
  assert {
    condition     = !var.enable_action_broker || var.env != "prod" || var.min_instance_count_broker >= 1
    error_message = "Action Broker in prod must keep min_instance_count_broker >= 1 to avoid cold-start latency on approval execution."
  }
}

check "agents_depend_on_eventing" {
  assert {
    condition     = length(local.active_agent_keys) == 0 || var.enable_eventing
    error_message = "Cannot enable agents without enable_eventing = true (agents need ops.audit / ops.notifications / ops.findings)."
  }
}

check "orchestrator_depends_on_signals" {
  assert {
    condition     = !local.agent_enabled.orchestrator || var.enable_eventing
    error_message = "The orchestrator subscribes to ops.signals, which is created by enable_eventing."
  }
}

check "notifier_requires_governance_token_or_inline" {
  assert {
    condition     = !var.enable_observability || var.slack_auth_token != "" || var.env != "prod"
    error_message = "observability in prod requires a real slack_auth_token (inject via CI)."
  }
}

# ---------------------------------------------------------------------------
# Foundation
# ---------------------------------------------------------------------------

module "foundation" {
  source = "../foundation"
  count  = var.enable_foundation ? 1 : 0

  project_id               = var.project_id
  region                   = var.region
  env                      = var.env
  essential_contacts_email = var.essential_contacts_email
  org_id                   = var.org_id
  folder_id                = var.folder_id
  labels                   = var.labels
}

# ---------------------------------------------------------------------------
# Eventing
# ---------------------------------------------------------------------------

module "eventing" {
  source = "../eventing"
  count  = var.enable_eventing ? 1 : 0

  project_id          = var.project_id
  env                 = var.env
  region              = var.region
  audit_bq_dataset_id = local.audit_bq_dataset_id

  labels = var.labels

  depends_on = [module.foundation]
}

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

module "governance" {
  source = "../governance"
  count  = var.enable_governance ? 1 : 0

  project_id                    = var.project_id
  env                           = var.env
  region                        = var.region
  org_id                        = var.org_id
  folder_id                     = var.folder_id
  audit_bq_dataset_id           = local.audit_bq_dataset_id
  scc_notification_pubsub_topic = var.enable_eventing ? module.eventing[0].ops_signals_topic_id : ""

  labels = var.labels

  depends_on = [module.foundation, module.eventing]
}

# ---------------------------------------------------------------------------
# Slack notifier (Cloud Run)
# ---------------------------------------------------------------------------

module "slack_notifier" {
  source = "../slack-notifier"
  count  = var.enable_slack_notifier ? 1 : 0

  project_id                    = var.project_id
  env                           = var.env
  region                        = var.region
  container_image               = local.default_image_notifier
  ops_notifications_topic_id    = var.enable_eventing ? module.eventing[0].ops_notifications_topic_id : ""
  ops_actions_approved_topic_id = var.enable_eventing ? module.eventing[0].ops_actions_approved_topic_id : ""
  slack_channel_incidents       = var.slack_channel_incidents
  slack_channel_security        = var.slack_channel_security
  slack_channel_finops          = var.slack_channel_finops
  slack_channel_platform        = var.slack_channel_platform
  min_instance_count            = var.min_instance_count_notifier

  labels = var.labels

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Action broker (Cloud Run)
# ---------------------------------------------------------------------------

module "action_broker" {
  source = "../action-broker"
  count  = var.enable_action_broker ? 1 : 0

  project_id                         = var.project_id
  env                                = var.env
  region                             = var.region
  container_image                    = local.default_image_broker
  ops_actions_approved_topic_id      = var.enable_eventing ? module.eventing[0].ops_actions_approved_topic_id : ""
  ops_actions_requested_topic_id     = var.enable_eventing ? module.eventing[0].ops_actions_requested_topic_id : ""
  ops_actions_executed_topic_id      = var.enable_eventing ? module.eventing[0].ops_actions_executed_topic_id : ""
  ops_audit_topic_id                 = var.enable_eventing ? module.eventing[0].ops_audit_topic_id : ""
  min_instance_count                 = var.min_instance_count_broker
  workflows_invoker_resource_pattern = var.workflows_invoker_resource_pattern

  labels = var.labels

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Observability (depends on broker + notifier URLs for uptime checks)
# ---------------------------------------------------------------------------

module "observability" {
  source = "../observability"
  count  = var.enable_observability ? 1 : 0

  project_id                 = var.project_id
  env                        = var.env
  region                     = var.region
  slack_auth_token           = var.slack_auth_token
  slack_auth_token_version   = var.slack_auth_token_version
  slack_workspace_id         = var.slack_workspace_id
  slack_channel_incidents    = var.slack_channel_incidents
  slack_channel_security     = var.slack_channel_security
  ops_notifications_topic_id = var.enable_eventing ? module.eventing[0].ops_notifications_topic_id : ""
  broker_url                 = var.enable_action_broker ? module.action_broker[0].service_url : "https://action-broker-placeholder.example.com"
  notifier_url               = var.enable_slack_notifier ? module.slack_notifier[0].service_url : "https://slack-notifier-placeholder.example.com"

  labels = var.labels

  depends_on = [module.slack_notifier, module.action_broker]
}

# ---------------------------------------------------------------------------
# Agents — each is independently optional.
# ---------------------------------------------------------------------------

module "agent_orchestrator" {
  source = "../agents/orchestrator"
  count  = local.agent_enabled.orchestrator ? 1 : 0

  project_id                 = var.project_id
  region                     = var.region
  env                        = var.env
  ops_signals_topic_id       = module.eventing[0].ops_signals_topic_id
  ops_notifications_topic_id = module.eventing[0].ops_notifications_topic_id
  ops_audit_topic_id         = module.eventing[0].ops_audit_topic_id
  deletion_policy_prevent    = var.deletion_policy_prevent
  enable_memory_bank         = try(var.enabled_agents["orchestrator"].enable_memory_bank, false)
  package_pickle_gcs_uri     = try(var.enabled_agents["orchestrator"].package_pickle_gcs_uri, "")
  schedule                   = try(var.enabled_agents["orchestrator"].schedule, null)
  labels                     = merge(var.labels, try(var.enabled_agents["orchestrator"].labels, {}))

  depends_on = [module.eventing]
}

module "agent_sre" {
  source = "../agents/sre"
  count  = local.agent_enabled.sre ? 1 : 0

  project_id                 = var.project_id
  region                     = var.region
  env                        = var.env
  ops_findings_topic_id      = module.eventing[0].ops_findings_topic_id
  ops_notifications_topic_id = module.eventing[0].ops_notifications_topic_id
  ops_audit_topic_id         = module.eventing[0].ops_audit_topic_id
  deletion_policy_prevent    = var.deletion_policy_prevent
  package_pickle_gcs_uri     = try(var.enabled_agents["sre"].package_pickle_gcs_uri, "")
  schedule                   = try(var.enabled_agents["sre"].schedule, null)
  labels                     = merge(var.labels, try(var.enabled_agents["sre"].labels, {}))

  depends_on = [module.eventing]
}

module "agent_devsecops" {
  source = "../agents/devsecops"
  count  = local.agent_enabled.devsecops ? 1 : 0

  project_id                 = var.project_id
  region                     = var.region
  env                        = var.env
  ops_findings_topic_id      = module.eventing[0].ops_findings_topic_id
  ops_notifications_topic_id = module.eventing[0].ops_notifications_topic_id
  ops_audit_topic_id         = module.eventing[0].ops_audit_topic_id
  deletion_policy_prevent    = var.deletion_policy_prevent
  package_pickle_gcs_uri     = try(var.enabled_agents["devsecops"].package_pickle_gcs_uri, "")
  schedule                   = try(var.enabled_agents["devsecops"].schedule, null)
  labels                     = merge(var.labels, try(var.enabled_agents["devsecops"].labels, {}))

  depends_on = [module.eventing]
}

module "agent_platform" {
  source = "../agents/platform"
  count  = local.agent_enabled.platform ? 1 : 0

  project_id                 = var.project_id
  region                     = var.region
  env                        = var.env
  ops_findings_topic_id      = module.eventing[0].ops_findings_topic_id
  ops_notifications_topic_id = module.eventing[0].ops_notifications_topic_id
  ops_audit_topic_id         = module.eventing[0].ops_audit_topic_id
  deletion_policy_prevent    = var.deletion_policy_prevent
  package_pickle_gcs_uri     = try(var.enabled_agents["platform"].package_pickle_gcs_uri, "")
  schedule                   = try(var.enabled_agents["platform"].schedule, null)
  labels                     = merge(var.labels, try(var.enabled_agents["platform"].labels, {}))

  depends_on = [module.eventing]
}

module "agent_finops" {
  source = "../agents/finops"
  count  = local.agent_enabled.finops ? 1 : 0

  project_id                   = var.project_id
  region                       = var.region
  env                          = var.env
  ops_findings_topic_id        = module.eventing[0].ops_findings_topic_id
  ops_notifications_topic_id   = module.eventing[0].ops_notifications_topic_id
  ops_audit_topic_id           = module.eventing[0].ops_audit_topic_id
  deletion_policy_prevent      = var.deletion_policy_prevent
  billing_export_bq_dataset_id = var.finops_billing_export_bq_dataset_id
  billing_export_bq_project_id = var.finops_billing_export_bq_project_id
  package_pickle_gcs_uri       = try(var.enabled_agents["finops"].package_pickle_gcs_uri, "")
  schedule                     = try(var.enabled_agents["finops"].schedule, null)
  labels                       = merge(var.labels, try(var.enabled_agents["finops"].labels, {}))

  depends_on = [module.eventing]
}

# ---------------------------------------------------------------------------
# Cross-cutting IAM — give every enabled agent SA run.invoker on the broker.
# Done here (not inside the broker module) so the broker can be applied first;
# the binding is composed once both modules have produced their outputs.
# ---------------------------------------------------------------------------

locals {
  agent_sa_members = compact([
    local.agent_enabled.orchestrator ? module.agent_orchestrator[0].sa_member : "",
    local.agent_enabled.sre ? module.agent_sre[0].sa_member : "",
    local.agent_enabled.devsecops ? module.agent_devsecops[0].sa_member : "",
    local.agent_enabled.platform ? module.agent_platform[0].sa_member : "",
    local.agent_enabled.finops ? module.agent_finops[0].sa_member : "",
  ])
}

resource "google_cloud_run_v2_service_iam_member" "agent_invoke_broker" {
  for_each = var.enable_action_broker ? toset(local.agent_sa_members) : []

  project  = var.project_id
  location = var.region
  name     = "action-broker"
  role     = "roles/run.invoker"
  member   = each.value

  depends_on = [module.action_broker]
}
