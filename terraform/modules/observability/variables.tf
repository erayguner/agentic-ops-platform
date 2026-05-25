variable "project_id" {
  type        = string
  description = "GCP project ID where observability resources are created."
}

variable "env" {
  type        = string
  description = "Environment name (dev|prod)."
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be 'dev' or 'prod'."
  }
}

variable "region" {
  type        = string
  description = "Default GCP region."
  default     = "europe-west2"
}

variable "slack_auth_token" {
  type        = string
  description = "Slack OAuth bot token for the monitoring notification channel. Written once; use auth_token_wo semantics."
  sensitive   = true
  default     = "REPLACE_WITH_SLACK_TOKEN" # placeholder — never commit the real value
}

variable "slack_auth_token_version" {
  type        = string
  description = "Monotonic integer version for the Slack token write-only attribute. Increment to rotate."
  default     = "1"
}

variable "slack_channel_incidents" {
  type        = string
  description = "Slack channel name for Critical/High operational alerts."
  default     = "#ops-incidents"
}

variable "slack_channel_security" {
  type        = string
  description = "Slack channel name for DevSecOps alerts."
  default     = "#ops-security"
}

variable "slack_workspace_id" {
  type        = string
  description = "Slack workspace (team) ID. Required for the native Slack notification channel. Obtain from Slack admin."
  default     = "REPLACE_WITH_WORKSPACE_ID" # placeholder
}

variable "ops_notifications_topic_id" {
  type        = string
  description = "Resource ID of the ops.notifications Pub/Sub topic (used for redundant Critical alert channel)."
}

variable "broker_url" {
  type        = string
  description = "HTTPS URL of the action-broker Cloud Run service (used for uptime check)."
  default     = "https://action-broker-placeholder.example.com"
}

variable "notifier_url" {
  type        = string
  description = "HTTPS URL of the slack-notifier Cloud Run service (used for uptime check)."
  default     = "https://slack-notifier-placeholder.example.com"
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
