variable "project_id" {
  type        = string
  description = "GCP project ID where eventing resources are created."
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

variable "audit_bq_dataset_id" {
  type        = string
  description = "BigQuery dataset ID for the ops.audit BQ subscription destination."
}

variable "audit_bq_table_id" {
  type        = string
  description = "BigQuery table ID for the ops.audit BQ subscription."
  default     = "audit_events"
}

variable "slack_notifier_url" {
  type        = string
  description = "HTTPS URL of the Slack-notifier Cloud Run service (for Eventarc trigger destination)."
  default     = "https://slack-notifier-placeholder.example.com"
}

variable "deletion_policy_prevent" {
  type        = bool
  description = "If true, set deletion_policy=ABANDON on ops.audit to guard against accidental destroy in prod."
  default     = false
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
