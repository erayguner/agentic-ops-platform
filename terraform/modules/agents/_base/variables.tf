variable "project_id" {
  type        = string
  description = "GCP project ID for the agent resources."
}

variable "region" {
  type        = string
  description = "GCP region for the reasoning engine."
}

variable "env" {
  type        = string
  description = "Environment slug used in labels and resource descriptions."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of 'dev', 'staging', 'prod'."
  }
}

variable "agent_slug" {
  type        = string
  description = "Short, lowercase slug identifying the agent (e.g. 'sre', 'orchestrator'). Becomes part of the SA account_id and resource names."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.agent_slug))
    error_message = "agent_slug must be 3-30 chars, lowercase alphanumerics or '-', starting with a letter."
  }
}

variable "agent_display_name" {
  type        = string
  description = "Human-readable name for the agent (used on the reasoning engine display_name)."
}

variable "agent_description" {
  type        = string
  description = "Short description of the agent's responsibilities. Surfaced in IAM and Vertex consoles."
}

variable "service_account_description" {
  type        = string
  description = "Description for the agent's GCP service account."
  default     = ""
}

variable "package_pickle_gcs_uri" {
  type        = string
  description = "GCS URI of the agent's pickled ADK package (gs://bucket/path/agent.pkl). Use a placeholder until your CI publishes the artefact."
  default     = ""
}

variable "package_python_version" {
  type        = string
  description = "Python runtime version for the reasoning engine."
  default     = "3.12"
}

variable "package_requirements_gcs_uri" {
  type        = string
  description = "Optional GCS URI of a requirements.txt for the reasoning engine."
  default     = ""
}

variable "agent_framework" {
  type        = string
  description = "Agent framework label for Vertex AI Reasoning Engine."
  default     = "google-adk"
}

variable "deletion_policy_prevent" {
  type        = bool
  description = "If true, sets deletion_policy=PREVENT on the reasoning engine. SHOULD be true in prod."
  default     = false
}

variable "enable_memory_bank" {
  type        = bool
  description = "If true, also provision a second reasoning engine that opts into Vertex Memory Bank (uses the beta provider)."
  default     = false
}

variable "ops_audit_topic_id" {
  type        = string
  description = "Resource ID of the ops.audit Pub/Sub topic. Every agent SA gets pubsub.publisher on this topic — missing this grant breaks audit emission silently."
}

variable "extra_pubsub_publish_topic_ids" {
  type        = list(string)
  description = "Additional Pub/Sub topic IDs the agent SA should be able to publish to (e.g. ops.notifications, ops.findings)."
  default     = []
}

variable "extra_pubsub_subscribe_topic_ids" {
  type        = list(string)
  description = "Pub/Sub topic IDs the agent SA should be able to subscribe to."
  default     = []
}

variable "project_iam_roles" {
  type        = list(string)
  description = "Project-scoped predefined roles to grant to the agent SA. Use only read-only roles — write actions go through the Action Broker."
  default     = []
  validation {
    condition = alltrue([
      for r in var.project_iam_roles :
      !contains(["roles/owner", "roles/editor"], r)
    ])
    error_message = "Refusing to grant roles/owner or roles/editor to an agent SA. Use least-privilege roles."
  }
}

variable "custom_project_iam_role_ids" {
  type        = list(string)
  description = "Custom project IAM role IDs to grant to the agent SA (e.g. projects/<p>/roles/aopAgentReader)."
  default     = []
}

variable "schedule" {
  type = object({
    cron       = optional(string)
    target_uri = optional(string)
    timezone   = optional(string, "Etc/UTC")
    body       = optional(string, "{}")
    headers    = optional(map(string), {})
  })
  description = <<-EOT
    Optional Cloud Scheduler trigger that pokes the agent on a cron schedule.
    Either supply a target_uri (HTTPS endpoint the agent SA can invoke) OR omit
    schedule entirely. When schedule.cron is non-null, a Cloud Scheduler job is
    created that runs `cron` in `timezone`, POSTing `body` (with `headers`) to
    `target_uri` using OIDC auth as the agent SA.
  EOT
  default     = null
  validation {
    condition = (
      var.schedule == null ||
      (var.schedule.cron != null && var.schedule.target_uri != null)
    )
    error_message = "When `schedule` is set, both `cron` and `target_uri` are required."
  }
}

variable "labels" {
  type        = map(string)
  description = "Additional labels merged with the standard AOP label set."
  default     = {}
}
