variable "project_id" {
  type        = string
  description = "GCP project ID for the dev environment (e.g. 'ops-agents-dev')."
}

variable "region" {
  type        = string
  description = "Default GCP region."
  default     = "europe-west2"
}

variable "org_id" {
  type        = string
  description = "GCP organisation ID. Empty if no org exists."
  default     = ""
}

variable "folder_id" {
  type        = string
  description = "GCP folder ID. Empty if no folder hierarchy exists."
  default     = ""
}

variable "essential_contacts_email" {
  type        = string
  description = "Email address for essential contacts."
}

variable "slack_auth_token" {
  type        = string
  description = "Slack OAuth bot token for the monitoring notification channel."
  sensitive   = true
}

variable "slack_auth_token_version" {
  type        = string
  description = "Monotonic version for Slack token rotation."
  default     = "1"
}

variable "slack_workspace_id" {
  type        = string
  description = "Slack workspace (team) ID."
}

variable "slack_channel_incidents" {
  type        = string
  description = "Slack channel for incidents."
  default     = "#ops-incidents"
}

variable "slack_channel_security" {
  type        = string
  description = "Slack channel for security findings."
  default     = "#ops-security"
}

variable "slack_channel_finops" {
  type        = string
  description = "Slack channel for FinOps alerts."
  default     = "#ops-finops"
}

variable "slack_channel_platform" {
  type        = string
  description = "Slack channel for platform alerts."
  default     = "#ops-platform"
}

variable "container_image_slack_notifier" {
  type        = string
  description = "Container image for the Slack notifier."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/slack-notifier:latest"
}

variable "container_image_action_broker" {
  type        = string
  description = "Container image for the action broker."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/action-broker:latest"
}
