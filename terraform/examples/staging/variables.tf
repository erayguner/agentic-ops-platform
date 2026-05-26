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

variable "slack_workspace_id" {
  type = string
}

variable "essential_contacts_email" {
  type    = string
  default = "platform-staging@example.com"
}

variable "finops_billing_export_bq_dataset_id" {
  type    = string
  default = ""
}
