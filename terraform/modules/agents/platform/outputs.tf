output "sa_email" {
  description = "Email of the Platform service account."
  value       = module.base.sa_email
}

output "sa_member" {
  description = "IAM member string for the Platform service account."
  value       = module.base.sa_member
}

output "reasoning_engine_id" {
  description = "Resource ID of the Platform reasoning engine."
  value       = module.base.reasoning_engine_id
}

output "scheduler_job_id" {
  description = "Optional Cloud Scheduler job ID."
  value       = module.base.scheduler_job_id
}
