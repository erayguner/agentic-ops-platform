output "sa_email" {
  description = "Email of the Decommission service account (read-only)."
  value       = module.base.sa_email
}

output "sa_member" {
  description = "IAM member string for the Decommission service account."
  value       = module.base.sa_member
}

output "reasoning_engine_id" {
  description = "Resource ID of the Decommission reasoning engine."
  value       = module.base.reasoning_engine_id
}

output "scheduler_job_id" {
  description = "Optional Cloud Scheduler job ID for the closure sweep."
  value       = module.base.scheduler_job_id
}

output "predefined_roles" {
  description = "The read-only roles granted to the Decommission SA."
  value       = local.predefined_roles
}
