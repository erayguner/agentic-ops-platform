variable "project_id" {
  type        = string
  description = "Downstream consumer's GCP project for AOP."
}

variable "region" {
  type    = string
  default = "europe-west2"
}

variable "env" {
  type    = string
  default = "dev"
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
  type = string
}

# Pin the framework version. Downstream consumers should keep this in sync
# with what their CI validates against. Use a tag (vX.Y.Z) — never a branch.
variable "aop_framework_version" {
  type    = string
  default = "v0.8.0" # x-release-please-version
}
