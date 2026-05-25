output "service_url" {
  description = "HTTPS URL of the slack-notifier Cloud Run service."
  value       = google_cloud_run_v2_service.slack_notifier.uri
}

output "sa_slack_notifier_email" {
  description = "Service account email of the slack-notifier."
  value       = google_service_account.slack_notifier.email
}

output "slack_oauth_token_secret_id" {
  description = "Secret Manager secret ID for the Slack OAuth token."
  value       = google_secret_manager_secret.slack_oauth_token.secret_id
}

output "slack_signing_secret_secret_id" {
  description = "Secret Manager secret ID for the Slack signing secret."
  value       = google_secret_manager_secret.slack_signing_secret.secret_id
}
