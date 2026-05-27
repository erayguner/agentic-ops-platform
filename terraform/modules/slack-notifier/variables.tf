variable "project_id" {
  type        = string
  description = "GCP project ID where slack-notifier resources are created."
}

variable "env" {
  type        = string
  description = "Environment name (dev|staging|prod)."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be 'dev', 'staging', or 'prod'."
  }
}

variable "region" {
  type        = string
  description = "GCP region for the Cloud Run service."
  default     = "europe-west2"
}

variable "container_image" {
  type        = string
  description = "Container image URI for the slack-notifier service."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/slack-notifier:latest"
}

variable "ops_notifications_topic_id" {
  type        = string
  description = "Resource ID of the ops.notifications Pub/Sub topic (notifier subscribes)."
}

variable "ops_actions_approved_topic_id" {
  type        = string
  description = "Resource ID of the ops.actions.approved Pub/Sub topic (notifier publishes approval decisions)."
}

variable "slack_channel_incidents" {
  type        = string
  description = "Primary Slack channel for operational incidents."
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
  description = "Slack channel for platform engineering alerts."
  default     = "#ops-platform"
}

variable "min_instance_count" {
  type        = number
  description = "Minimum Cloud Run instances."
  default     = 0
}

variable "max_instance_count" {
  type        = number
  description = "Maximum Cloud Run instances."
  default     = 3
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
