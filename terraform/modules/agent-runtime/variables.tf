variable "project_id" {
  type        = string
  description = "GCP project ID where agent runtime resources are created."
}

variable "env" {
  type        = string
  description = "Environment name (dev|prod)."
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be 'dev' or 'prod'."
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
