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

variable "enable_bq_audit_subscription" {
  type        = bool
  description = <<-EOT
    Create the ops.audit -> BigQuery subscription (and the Pub/Sub service-agent
    BigQuery IAM it needs). Default true. NOTE: with use_topic_schema=true the
    ops.audit AVRO schema must be compatible with the audit_events BQ table
    schema; they currently diverge (e.g. evidence_refs is repeated in AVRO but
    JSON in BQ), so set false until the schemas are reconciled.
  EOT
  default     = true
}

variable "enable_eventarc_triggers" {
  type        = bool
  description = <<-EOT
    Create the two Eventarc triggers (audit-logs->orchestrator and
    ops.notifications->slack-notifier). Default true preserves legacy dev/prod
    behaviour. Set false for a clean first apply when the Cloud Run
    destinations ('orchestrator', 'slack-notifier') do not yet exist; wire the
    triggers in on a follow-up apply once those services are deployed.
  EOT
  default     = true
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
