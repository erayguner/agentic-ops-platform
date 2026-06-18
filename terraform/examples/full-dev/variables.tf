variable "project_id" {
  type    = string
  default = "ops-agents-dev"
}

variable "region" {
  type    = string
  default = "europe-west2"
}

variable "slack_auth_token" {
  type      = string
  sensitive = true
  default   = ""
}

variable "slack_workspace_id" {
  type    = string
  default = ""
}

variable "essential_contacts_email" {
  type    = string
  default = "platform-owner@example.com"
}
