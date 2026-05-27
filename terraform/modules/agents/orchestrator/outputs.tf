output "sa_email" {
  description = "Email of the orchestrator service account."
  value       = module.base.sa_email
}

output "sa_member" {
  description = "IAM member string for the orchestrator service account."
  value       = module.base.sa_member
}

output "reasoning_engine_id" {
  description = "Resource ID of the orchestrator reasoning engine."
  value       = module.base.reasoning_engine_id
}

output "memory_bank_reasoning_engine_id" {
  description = "Resource ID of the optional Memory Bank reasoning engine; empty when disabled."
  value       = module.base.memory_bank_reasoning_engine_id
}

output "scheduler_job_id" {
  description = "Resource ID of the optional Cloud Scheduler job; empty when no schedule."
  value       = module.base.scheduler_job_id
}
