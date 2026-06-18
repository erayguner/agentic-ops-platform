variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west2"
}

variable "slack_auth_token" {
  type      = string
  sensitive = true
}

variable "slack_auth_token_version" {
  type    = string
  default = "1"
}

variable "slack_workspace_id" {
  type = string
}

variable "essential_contacts_email" {
  type = string
}

variable "finops_billing_export_bq_dataset_id" {
  type        = string
  description = "Required in prod — dataset-scoped IAM."
}

variable "finops_billing_export_bq_project_id" {
  type    = string
  default = ""
}

variable "container_image_action_broker" {
  type        = string
  description = "Pinned (digest-style) image for prod."
}

variable "container_image_slack_notifier" {
  type        = string
  description = "Pinned image for prod."
}

variable "workflows_invoker_resource_pattern" {
  type        = string
  description = "Resource-name prefix that scopes the broker's workflows.invoker grant (e.g. 'aop-')."
  default     = "aop-"
}
