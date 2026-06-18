variable "project_id" {
  type        = string
  description = "GCP project ID where governance resources are created."
}

variable "env" {
  type        = string
  description = "Environment name (dev|staging|prod)."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be 'dev', 'staging', or 'prod'."
  }
}

variable "deletion_policy_prevent" {
  type        = bool
  description = "When true, the audit BigQuery dataset is created with deletion_policy = PREVENT so a terraform destroy or resource replacement cannot drop the compliance audit store. Set true in prod (mirrors agent-runtime / ops.audit topic protection)."
  default     = false
}

variable "delete_contents_on_destroy" {
  type        = bool
  description = "When true, terraform destroy drops the audit dataset even if it contains tables auto-created by the log sink (which Terraform does not manage). Dev/test only; false in prod."
  default     = false
}

variable "region" {
  type        = string
  description = "Default GCP region."
  default     = "europe-west2"
}

variable "org_id" {
  type        = string
  description = "GCP organisation ID. Required for org-scoped SCC and Org Policy. Leave empty to skip those resources."
  default     = ""
}

variable "folder_id" {
  type        = string
  description = "GCP folder ID. Used for folder-scoped Org Policy variants. Leave empty to skip."
  default     = ""
}

variable "audit_bq_dataset_id" {
  type        = string
  description = "BigQuery dataset ID for audit log export (e.g. 'audit_logs')."
  default     = "audit_logs"
}

variable "audit_bq_table_id" {
  type        = string
  description = "BigQuery table ID for SCC BQ export."
  default     = "scc_findings"
}

variable "scc_notification_pubsub_topic" {
  type        = string
  description = "Full Pub/Sub topic resource name for SCC notifications (e.g. projects/<id>/topics/ops.signals). Only used when enable_scc = true."
  default     = ""
}

variable "enable_org_policies" {
  type        = bool
  description = <<-EOT
    Create the project-scoped Org Policy constraints (disable SA key creation,
    EU resource-location restriction). Requires the project to belong to a GCP
    organization AND orgpolicy.googleapis.com enabled — standalone projects with
    no org cannot set org policies. Default false (safe for no-org projects).
  EOT
  default     = false
}

variable "enable_scc" {
  type        = bool
  description = <<-EOT
    Create the project-scoped Security Command Center notification config and
    BigQuery export. SCC (all tiers, including free Standard) is activated at the
    organization level; standalone projects with no org cannot use it. Default
    false. Requires scc_notification_pubsub_topic when true.
  EOT
  default     = false
}

variable "enable_model_armor" {
  type        = bool
  description = <<-EOT
    Create the Model Armor floor setting + default template (prompt-injection,
    RAI, malicious-URI, sensitive-data screening). Requires modelarmor.googleapis.com
    and a supported model_armor_location. Default true (security baseline); set
    false to skip when no agent traffic is screened yet or for a minimal-risk apply.
  EOT
  default     = true
}

variable "model_armor_location" {
  type        = string
  description = "Location for Model Armor resources."
  default     = "global"
}

variable "log_sink_name" {
  type        = string
  description = "Name of the project-level log sink to BigQuery."
  default     = "aop-audit-sink"
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
