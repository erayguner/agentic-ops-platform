output "topic_ids" {
  description = "Pub/Sub topics surfaced by the framework."
  value       = module.aop.topic_ids
}

output "agent_sa_emails" {
  description = "Agent SAs the downstream team can grant IAM to."
  value       = module.aop.agent_sa_emails
}

output "framework_version" {
  description = "Pinned version of the AOP framework this consumer is using."
  value       = var.aop_framework_version
}
