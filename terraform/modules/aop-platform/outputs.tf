output "project_id" {
  description = "Project the platform was deployed into."
  value       = var.project_id
}

output "env" {
  description = "Environment slug."
  value       = var.env
}

output "region" {
  description = "Region the platform was deployed into."
  value       = var.region
}

# ---------------------------------------------------------------------------
# Foundation
# ---------------------------------------------------------------------------

output "vpc_id" {
  description = "Foundation VPC self-link, or empty when foundation was disabled."
  value       = var.enable_foundation ? module.foundation[0].vpc_id : ""
}

output "artifact_registry_repo_url" {
  description = "Push URL for the AOP container Artifact Registry repository."
  value       = var.enable_foundation ? module.foundation[0].artifact_registry_repo_url : ""
}

# ---------------------------------------------------------------------------
# Eventing
# ---------------------------------------------------------------------------

output "topic_ids" {
  description = "Map of canonical AOP Pub/Sub topic IDs (empty when eventing is disabled)."
  value = var.enable_eventing ? {
    ops_signals           = module.eventing[0].ops_signals_topic_id
    ops_findings          = module.eventing[0].ops_findings_topic_id
    ops_actions_requested = module.eventing[0].ops_actions_requested_topic_id
    ops_actions_approved  = module.eventing[0].ops_actions_approved_topic_id
    ops_actions_executed  = module.eventing[0].ops_actions_executed_topic_id
    ops_notifications     = module.eventing[0].ops_notifications_topic_id
    ops_audit             = module.eventing[0].ops_audit_topic_id
  } : {}
}

# ---------------------------------------------------------------------------
# Cloud Run service URLs
# ---------------------------------------------------------------------------

output "action_broker_url" {
  description = "HTTPS URL of the action-broker service."
  value       = var.enable_action_broker ? module.action_broker[0].service_url : ""
}

output "slack_notifier_url" {
  description = "HTTPS URL of the slack-notifier service."
  value       = var.enable_slack_notifier ? module.slack_notifier[0].service_url : ""
}

# ---------------------------------------------------------------------------
# Agent identities — empty when the agent is not enabled.
# ---------------------------------------------------------------------------

output "agent_sa_emails" {
  description = "Map of agent slug → service-account email for each enabled agent."
  value = {
    orchestrator = local.agent_enabled.orchestrator ? module.agent_orchestrator[0].sa_email : ""
    sre          = local.agent_enabled.sre ? module.agent_sre[0].sa_email : ""
    devsecops    = local.agent_enabled.devsecops ? module.agent_devsecops[0].sa_email : ""
    platform     = local.agent_enabled.platform ? module.agent_platform[0].sa_email : ""
    finops       = local.agent_enabled.finops ? module.agent_finops[0].sa_email : ""
  }
}

output "agent_reasoning_engine_ids" {
  description = "Map of agent slug → reasoning-engine resource ID for each enabled agent."
  value = {
    orchestrator = local.agent_enabled.orchestrator ? module.agent_orchestrator[0].reasoning_engine_id : ""
    sre          = local.agent_enabled.sre ? module.agent_sre[0].reasoning_engine_id : ""
    devsecops    = local.agent_enabled.devsecops ? module.agent_devsecops[0].reasoning_engine_id : ""
    platform     = local.agent_enabled.platform ? module.agent_platform[0].reasoning_engine_id : ""
    finops       = local.agent_enabled.finops ? module.agent_finops[0].reasoning_engine_id : ""
  }
}

output "agent_scheduler_job_ids" {
  description = "Map of agent slug → Cloud Scheduler job ID (empty when the agent has no schedule)."
  value = {
    orchestrator = local.agent_enabled.orchestrator ? module.agent_orchestrator[0].scheduler_job_id : ""
    sre          = local.agent_enabled.sre ? module.agent_sre[0].scheduler_job_id : ""
    devsecops    = local.agent_enabled.devsecops ? module.agent_devsecops[0].scheduler_job_id : ""
    platform     = local.agent_enabled.platform ? module.agent_platform[0].scheduler_job_id : ""
    finops       = local.agent_enabled.finops ? module.agent_finops[0].scheduler_job_id : ""
  }
}

# ---------------------------------------------------------------------------
# Action broker per-action-class SAs (empty when broker is disabled)
# ---------------------------------------------------------------------------

output "action_broker_sa_email" {
  description = "Email of the Action Broker service account."
  value       = var.enable_action_broker ? module.action_broker[0].sa_action_broker_email : ""
}

output "action_class_sa_emails" {
  description = "Map of action-class slug → impersonation SA email."
  value = var.enable_action_broker ? {
    cloudrun_scale    = module.action_broker[0].sa_action_cloudrun_scale_email
    cloudrun_rollback = module.action_broker[0].sa_action_cloudrun_rollback_email
    iam_disable_key   = module.action_broker[0].sa_action_iam_disable_key_email
    secret_disable    = module.action_broker[0].sa_action_secret_disable_email
    scc_mute          = module.action_broker[0].sa_action_scc_mute_email
    workflows_run     = module.action_broker[0].sa_action_workflows_run_email
    terraform_plan    = module.action_broker[0].sa_action_terraform_plan_email
  } : {}
}

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

output "auditor_role_id" {
  description = "Full role ID of the AOP Auditor custom IAM role."
  value       = var.enable_governance ? module.governance[0].auditor_role_id : ""
}

output "audit_bq_dataset_id" {
  description = "BigQuery dataset that holds the audit log export."
  value       = var.enable_governance ? module.governance[0].audit_bq_dataset_id : local.audit_bq_dataset_id
}
