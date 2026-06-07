output "audit_bq_dataset_id" {
  description = "BigQuery dataset ID for audit log exports."
  value       = google_bigquery_dataset.audit_logs.dataset_id
}

output "audit_log_sink_writer_identity" {
  description = "Service account identity of the audit log sink writer."
  value       = google_logging_project_sink.audit_bq.writer_identity
}

output "model_armor_template_id" {
  description = "Resource ID of the default AOP Model Armor template (null when enable_model_armor = false)."
  value       = one(google_model_armor_template.aop_default[*].id)
}

output "scc_notification_config_name" {
  description = "Resource name of the AOP SCC project notification config (null when enable_scc = false)."
  value       = one(google_scc_project_notification_config.aop[*].name)
}

output "auditor_role_id" {
  description = "Full role ID of the AOP Auditor custom IAM role."
  value       = google_project_iam_custom_role.auditor.id
}
