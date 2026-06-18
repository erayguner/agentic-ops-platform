variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "region" {
  type        = string
  description = "GCP region."
  default     = "europe-west2"
}

variable "env" {
  type        = string
  description = "Environment slug."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of 'dev', 'staging', 'prod'."
  }
}

variable "ops_findings_topic_id" {
  type        = string
  description = "Resource ID of ops.findings (SRE publishes findings)."
}

variable "ops_notifications_topic_id" {
  type        = string
  description = "Resource ID of ops.notifications (SRE publishes notifications)."
}

variable "ops_audit_topic_id" {
  type        = string
  description = "Resource ID of ops.audit (SRE publishes audit records)."
}

variable "deletion_policy_prevent" {
  type        = bool
  description = "Set deletion_policy=PREVENT in prod."
  default     = false
}

variable "package_pickle_gcs_uri" {
  type        = string
  description = "GCS URI of the SRE agent's ADK package."
  default     = ""
}

variable "schedule" {
  type = object({
    cron       = optional(string)
    target_uri = optional(string)
    timezone   = optional(string, "Etc/UTC")
    body       = optional(string, "{}")
    headers    = optional(map(string), {})
  })
  description = "Optional Cloud Scheduler trigger (e.g. periodic burn-rate sweep)."
  default     = null
}

variable "labels" {
  type        = map(string)
  description = "Additional labels."
  default     = {}
}
