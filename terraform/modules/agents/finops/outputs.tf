output "sa_email" {
  description = "Email of the FinOps service account."
  value       = module.base.sa_email
}

output "sa_member" {
  description = "IAM member string for the FinOps service account."
  value       = module.base.sa_member
}

output "reasoning_engine_id" {
  description = "Resource ID of the FinOps reasoning engine."
  value       = module.base.reasoning_engine_id
}

output "scheduler_job_id" {
  description = "Optional Cloud Scheduler job ID."
  value       = module.base.scheduler_job_id
}

output "billing_export_scope_is_dataset" {
  description = "True if the FinOps BigQuery binding is dataset-scoped (preferred). False indicates the project-wide dataViewer fallback was used."
  value       = local.bq_scoped
}
