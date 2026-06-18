output "service_url" {
  description = "HTTPS URL of the action-broker Cloud Run service."
  value       = google_cloud_run_v2_service.action_broker.uri
}

output "sa_action_broker_email" {
  description = "Service account email of the action-broker."
  value       = google_service_account.action_broker.email
}

output "sa_action_cloudrun_scale_email" {
  description = "Service account email for cloud_run.scale_within_range actions."
  value       = google_service_account.action_cloudrun_scale.email
}

output "sa_action_cloudrun_rollback_email" {
  description = "Service account email for cloud_run.rollback_to_previous actions."
  value       = google_service_account.action_cloudrun_rollback.email
}

output "sa_action_iam_disable_key_email" {
  description = "Service account email for iam.disable_service_account_key actions."
  value       = google_service_account.action_iam_disable_key.email
}

output "sa_action_secret_disable_email" {
  description = "Service account email for secret_manager.disable_version actions."
  value       = google_service_account.action_secret_disable.email
}

output "sa_action_scc_mute_email" {
  description = "Service account email for scc.mute_finding actions."
  value       = google_service_account.action_scc_mute.email
}

output "sa_action_workflows_run_email" {
  description = "Service account email for workflows.run actions."
  value       = google_service_account.action_workflows_run.email
}

output "sa_action_terraform_plan_email" {
  description = "Service account email for terraform.plan actions."
  value       = google_service_account.action_terraform_plan.email
}
