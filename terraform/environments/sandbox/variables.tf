# Sandbox validation root — variables.
# Real values are provided in sandbox.auto.tfvars (gitignored). The committed
# terraform.tfvars holds placeholders only (no real IDs/tokens).

variable "project_id" {
  type        = string
  description = "Target GCP project ID for the deploy/destroy validation."
}

variable "project_number" {
  type        = string
  description = "Numeric project number (used by the billing budget filter)."
}

variable "region" {
  type        = string
  description = "Default GCP region for regional resources."
  default     = "europe-west2"
}

variable "org_id" {
  type        = string
  description = "GCP organisation ID. Empty for a standalone (no-org) project."
  default     = ""
}

variable "folder_id" {
  type        = string
  description = "GCP folder ID. Empty when no folder hierarchy exists."
  default     = ""
}

variable "essential_contacts_email" {
  type        = string
  description = "Email for Essential Contacts (security/billing/technical) and budget alerts."
}

variable "slack_channel_incidents" {
  type        = string
  description = "Slack channel for incidents (label only; no live Slack in validation)."
  default     = "#ops-incidents"
}

variable "slack_channel_security" {
  type        = string
  description = "Slack channel for security findings (label only)."
  default     = "#ops-security"
}

variable "slack_channel_finops" {
  type        = string
  description = "Slack channel for FinOps alerts (label only)."
  default     = "#ops-finops"
}

variable "slack_channel_platform" {
  type        = string
  description = "Slack channel for platform alerts (label only)."
  default     = "#ops-platform"
}

variable "container_image_slack_notifier" {
  type        = string
  description = "Container image URI for the slack-notifier Cloud Run service (built + pushed to Artifact Registry before the full apply)."
}

variable "container_image_action_broker" {
  type        = string
  description = "Container image URI for the action-broker Cloud Run service (built + pushed to Artifact Registry before the full apply)."
}

variable "billing_account_id" {
  type        = string
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX) for the cost-guardrail budget."
}

variable "budget_amount_usd" {
  type        = number
  description = "Monthly Cloud Billing budget amount in USD (alert-only; does not cap spend)."
  default     = 20
}
