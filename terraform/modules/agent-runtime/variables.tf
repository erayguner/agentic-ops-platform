variable "project_id" {
  type        = string
  description = "GCP project ID where agent runtime resources are created."
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
  description = "Default GCP region for Agent Engine deployments."
  default     = "europe-west2"
}

variable "container_image_orchestrator" {
  type        = string
  description = "Container image URI for the orchestrator agent."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/orchestrator:latest"
}

variable "container_image_sre" {
  type        = string
  description = "Container image URI for the SRE agent."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/sre:latest"
}

variable "container_image_devsecops" {
  type        = string
  description = "Container image URI for the DevSecOps agent."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/devsecops:latest"
}

variable "container_image_platform" {
  type        = string
  description = "Container image URI for the Platform Engineering agent."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/platform:latest"
}

variable "container_image_finops" {
  type        = string
  description = "Container image URI for the FinOps agent."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/finops:latest"
}

variable "deletion_policy_prevent" {
  type        = bool
  description = "If true, sets deletion_policy=PREVENT on all reasoning engines. Should be true in prod."
  default     = false
}

variable "ops_signals_topic_id" {
  type        = string
  description = "Resource ID of the ops.signals Pub/Sub topic (for IAM grants to orchestrator)."
}

variable "ops_findings_topic_id" {
  type        = string
  description = "Resource ID of the ops.findings Pub/Sub topic (for IAM grants to specialist agents)."
}

variable "ops_notifications_topic_id" {
  type        = string
  description = "Resource ID of the ops.notifications Pub/Sub topic. Orchestrator + every specialist receives pubsub.publisher on this topic (via aop_common.slack_emitter)."
}

variable "ops_audit_topic_id" {
  type        = string
  description = "Resource ID of the ops.audit Pub/Sub topic. EVERY agent SA receives pubsub.publisher on this topic so aop_common.audit.AuditEmitter can emit AuditRecord v1 events for each lifecycle phase. Missing this grant breaks audit emission silently."
}

variable "audit_bq_dataset_id" {
  type        = string
  description = "BigQuery dataset ID for audit table reference (kept for cross-module compatibility; no IAM is granted on this dataset from this module — agents do not read the audit table directly)."
  default     = "audit_logs"
}

variable "billing_export_bq_dataset_id" {
  type        = string
  description = <<-EOT
    BigQuery dataset ID that holds the Cloud Billing detailed export.
    When set, the FinOps agent receives roles/bigquery.dataViewer scoped to
    THIS DATASET ONLY (plus roles/bigquery.jobUser at project scope so it can
    run queries). When empty, the agent falls back to project-wide
    bigquery.dataViewer — looser, flagged as a known gap in
    docs/GOVERNANCE-MAPPING.md §11.8. Setting this to the actual billing
    export dataset (typically `billing_export` or similar) is the
    recommended posture for production.
  EOT
  default     = ""
}

variable "billing_export_bq_project_id" {
  type        = string
  description = "Project that hosts the billing export dataset, if different from project_id. Defaults to project_id when empty. Only consulted when billing_export_bq_dataset_id is set."
  default     = ""
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}

# ---------------------------------------------------------------------------
# Memory Bank (orchestrator context_spec) — OWASP §11.6 / ASI06.
# ---------------------------------------------------------------------------

variable "memory_generation_model" {
  type        = string
  description = "Short model id the orchestrator Memory Bank uses to generate memories (resolved to a Vertex publisher path). A low-cost model (e.g. gemini-2.5-flash) is recommended."
  default     = "gemini-2.5-flash"
}

variable "memory_embedding_model" {
  type        = string
  description = "Short embedding model id the Memory Bank uses for similarity search over stored memories (resolved to a Vertex publisher path)."
  default     = "text-embedding-005"
}

variable "memory_default_ttl" {
  type        = string
  description = "Retention policy for Memory Bank entries (OWASP §11.6: 'retention policy declared per memory store'). Expired memories are purged. Duration string in seconds, e.g. 2592000s = 30 days."
  default     = "2592000s"
  validation {
    condition     = can(regex("^[0-9]+s$", var.memory_default_ttl))
    error_message = "memory_default_ttl must be a duration in seconds, e.g. '2592000s'."
  }
}

# ---------------------------------------------------------------------------
# Agent runtime identity — code-artifact bucket for the per-agent SA.
# ---------------------------------------------------------------------------

variable "agent_artifact_bucket" {
  type        = string
  description = <<-EOT
    Cloud Storage bucket NAME (no gs:// prefix) holding the agents' deployed
    code artifacts. When set, each per-agent SA receives roles/storage.objectViewer
    scoped to THIS BUCKET ONLY, so the Agent Engine runtime can load its code
    under its own least-privilege identity. When empty (skeleton default), no
    storage grant is added — set this for a live deployment.
  EOT
  default     = ""
}
