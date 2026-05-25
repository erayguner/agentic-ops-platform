output "slack_notification_channel_id" {
  description = "Resource ID of the primary Slack notification channel."
  value       = google_monitoring_notification_channel.slack_primary.id
}

output "pubsub_notification_channel_id" {
  description = "Resource ID of the redundant Pub/Sub notification channel."
  value       = google_monitoring_notification_channel.pubsub_redundant.id
}

output "alert_agent_down_id" {
  description = "Resource name of the 'Agent down' alert policy."
  value       = google_monitoring_alert_policy.agent_down.name
}

output "alert_decision_latency_id" {
  description = "Resource name of the 'Decision latency p95' alert policy."
  value       = google_monitoring_alert_policy.decision_latency_p95.name
}

output "alert_rollback_rate_id" {
  description = "Resource name of the 'Action rollback rate' alert policy."
  value       = google_monitoring_alert_policy.action_rollback_rate.name
}

output "dashboard_overview_id" {
  description = "Resource name of the ops-platform-overview dashboard."
  value       = google_monitoring_dashboard.ops_platform_overview.id
}

output "broker_uptime_check_id" {
  description = "Uptime check ID for the action-broker."
  value       = google_monitoring_uptime_check_config.action_broker.uptime_check_id
}

output "notifier_uptime_check_id" {
  description = "Uptime check ID for the slack-notifier."
  value       = google_monitoring_uptime_check_config.slack_notifier.uptime_check_id
}
