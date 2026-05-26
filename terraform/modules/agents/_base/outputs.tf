output "agent_slug" {
  description = "Slug for this agent."
  value       = var.agent_slug
}

output "sa_email" {
  description = "Email of the agent's service account."
  value       = google_service_account.this.email
}

output "sa_name" {
  description = "Fully-qualified name of the agent's service account (projects/.../serviceAccounts/...)."
  value       = google_service_account.this.name
}

output "sa_member" {
  description = "IAM member string for the agent's service account."
  value       = "serviceAccount:${google_service_account.this.email}"
}

output "reasoning_engine_id" {
  description = "Resource ID of the reasoning engine."
  value       = google_vertex_ai_reasoning_engine.this.id
}

output "reasoning_engine_name" {
  description = "Short name of the reasoning engine."
  value       = google_vertex_ai_reasoning_engine.this.name
}

output "memory_bank_reasoning_engine_id" {
  description = "Resource ID of the optional Memory Bank reasoning engine; empty when not enabled."
  value       = var.enable_memory_bank ? google_vertex_ai_reasoning_engine.memory_bank[0].id : ""
}

output "scheduler_job_id" {
  description = "Resource ID of the optional Cloud Scheduler job; empty when no schedule was configured."
  value       = var.schedule != null ? google_cloud_scheduler_job.trigger[0].id : ""
}

output "labels" {
  description = "Effective labels applied to agent resources."
  value       = local.common_labels
}
