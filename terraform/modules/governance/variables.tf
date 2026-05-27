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
  description = "Full Pub/Sub topic resource name for SCC notifications (e.g. projects/<id>/topics/ops.signals)."
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
