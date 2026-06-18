output "sa_orchestrator_email" {
  description = "Service account email of the Orchestrator agent."
  value       = google_service_account.orchestrator.email
}

output "sa_sre_email" {
  description = "Service account email of the SRE agent."
  value       = google_service_account.sre.email
}

output "sa_devsecops_email" {
  description = "Service account email of the DevSecOps agent."
  value       = google_service_account.devsecops.email
}

output "sa_platform_email" {
  description = "Service account email of the Platform Engineering agent."
  value       = google_service_account.platform.email
}

output "sa_finops_email" {
  description = "Service account email of the FinOps agent."
  value       = google_service_account.finops.email
}

output "reasoning_engine_orchestrator_id" {
  description = "Resource ID of the Orchestrator reasoning engine."
  value       = google_vertex_ai_reasoning_engine.orchestrator.id
}

output "reasoning_engine_sre_id" {
  description = "Resource ID of the SRE reasoning engine."
  value       = google_vertex_ai_reasoning_engine.sre.id
}

output "reasoning_engine_devsecops_id" {
  description = "Resource ID of the DevSecOps reasoning engine."
  value       = google_vertex_ai_reasoning_engine.devsecops.id
}

output "reasoning_engine_platform_id" {
  description = "Resource ID of the Platform Engineering reasoning engine."
  value       = google_vertex_ai_reasoning_engine.platform.id
}

output "reasoning_engine_finops_id" {
  description = "Resource ID of the FinOps reasoning engine."
  value       = google_vertex_ai_reasoning_engine.finops.id
}
