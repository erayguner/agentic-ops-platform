output "ops_signals_topic_id" {
  description = "Resource ID of the ops.signals Pub/Sub topic."
  value       = google_pubsub_topic.ops_signals.id
}

output "ops_signals_topic_name" {
  description = "Name of the ops.signals Pub/Sub topic."
  value       = google_pubsub_topic.ops_signals.name
}

output "ops_findings_topic_id" {
  description = "Resource ID of the ops.findings Pub/Sub topic."
  value       = google_pubsub_topic.ops_findings.id
}

output "ops_actions_requested_topic_id" {
  description = "Resource ID of the ops.actions.requested Pub/Sub topic."
  value       = google_pubsub_topic.ops_actions_requested.id
}

output "ops_actions_approved_topic_id" {
  description = "Resource ID of the ops.actions.approved Pub/Sub topic."
  value       = google_pubsub_topic.ops_actions_approved.id
}

output "ops_actions_executed_topic_id" {
  description = "Resource ID of the ops.actions.executed Pub/Sub topic."
  value       = google_pubsub_topic.ops_actions_executed.id
}

output "ops_notifications_topic_id" {
  description = "Resource ID of the ops.notifications Pub/Sub topic."
  value       = google_pubsub_topic.ops_notifications.id
}

output "ops_audit_topic_id" {
  description = "Resource ID of the ops.audit Pub/Sub topic."
  value       = google_pubsub_topic.ops_audit.id
}

output "audit_events_table_id" {
  description = "Fully-qualified BigQuery table ID for audit events."
  value       = "${var.project_id}.${var.audit_bq_dataset_id}.${var.audit_bq_table_id}"
}
