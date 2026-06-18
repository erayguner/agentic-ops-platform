# ---------------------------------------------------------------------------
# Core identity & environment
# ---------------------------------------------------------------------------

variable "project_id" {
  type        = string
  description = "GCP project ID for all AOP resources."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be 6-30 chars, lowercase alphanumerics or '-', starting with a letter."
  }
}

variable "region" {
  type        = string
  description = "Primary GCP region. Module is region-pinned to keep EU data-residency simple."
  default     = "europe-west2"
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.region))
    error_message = "region must look like a GCP region (e.g. europe-west2)."
  }
}

variable "env" {
  type        = string
  description = "Environment slug — 'dev', 'staging', or 'prod'."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of 'dev', 'staging', 'prod'."
  }
}

variable "org_id" {
  type        = string
  description = "GCP organisation ID. Empty disables org-scoped governance controls."
  default     = ""
}

variable "folder_id" {
  type        = string
  description = "GCP folder ID. Empty disables folder-scoped Org Policy variants."
  default     = ""
}

# ---------------------------------------------------------------------------
# Component feature flags. Every layer is optional — set `enabled = false` to
# skip provisioning. The defaults give you a fully wired platform.
# ---------------------------------------------------------------------------

variable "enable_foundation" {
  type        = bool
  description = "Provision the foundation layer (VPC, Artifact Registry, Essential Contacts, API enablement)."
  default     = true
}

variable "enable_eventing" {
  type        = bool
  description = "Provision Pub/Sub topics, schemas, DLQs, BQ audit table, Eventarc."
  default     = true
}

variable "enable_governance" {
  type        = bool
  description = "Provision Model Armor, SCC notifications, Org Policy, audit sink, Auditor role."
  default     = true
}

variable "enable_observability" {
  type        = bool
  description = "Provision dashboards, alerts, log-based metrics, uptime checks, SLOs."
  default     = true
}

variable "enable_action_broker" {
  type        = bool
  description = "Provision the Action Broker Cloud Run service and per-action-class SAs."
  default     = true
}

variable "enable_slack_notifier" {
  type        = bool
  description = "Provision the Slack notifier Cloud Run service and secrets."
  default     = true
}

# ---------------------------------------------------------------------------
# Agent selection. Map shape lets callers pick which agents to deploy and pass
# per-agent overrides (custom schedule, custom labels, package URI) without
# adding a variable per agent.
# ---------------------------------------------------------------------------

variable "enabled_agents" {
  type = map(object({
    enabled                = optional(bool, true)
    enable_memory_bank     = optional(bool, false)
    package_pickle_gcs_uri = optional(string, "")
    labels                 = optional(map(string), {})

    schedule = optional(object({
      cron       = optional(string)
      target_uri = optional(string)
      timezone   = optional(string, "Etc/UTC")
      body       = optional(string, "{}")
      headers    = optional(map(string), {})
    }))
  }))
  description = <<-EOT
    Agents to provision. Keys must be a subset of:
      orchestrator, sre, devsecops, platform, finops

    Examples:
      enabled_agents = {
        sre          = {}
        devsecops    = { enabled_memory_bank = true }
      }

    Omitted agents are not deployed.
  EOT
  default = {
    orchestrator = {}
    sre          = {}
    devsecops    = {}
    platform     = {}
    finops       = {}
  }
  validation {
    condition = alltrue([
      for k, _ in var.enabled_agents :
      contains(["orchestrator", "sre", "devsecops", "platform", "finops"], k)
    ])
    error_message = "enabled_agents keys must be one of: orchestrator, sre, devsecops, platform, finops."
  }
}

# ---------------------------------------------------------------------------
# FinOps-specific configuration
# ---------------------------------------------------------------------------

variable "finops_billing_export_bq_dataset_id" {
  type        = string
  description = "BigQuery dataset that holds the Cloud Billing detailed export. Set this in prod to get dataset-scoped IAM."
  default     = ""
}

variable "finops_billing_export_bq_project_id" {
  type        = string
  description = "Project hosting the billing export dataset (defaults to project_id)."
  default     = ""
}

# ---------------------------------------------------------------------------
# Slack / notifier configuration
# ---------------------------------------------------------------------------

variable "essential_contacts_email" {
  type        = string
  description = "Email address subscribed to SECURITY/BILLING/TECHNICAL essential-contact notifications."
  default     = "platform-owner@example.com"
}

variable "slack_auth_token" {
  type        = string
  description = "Slack OAuth bot token for the monitoring channel. Inject via CI; never commit."
  sensitive   = true
  default     = ""
}

variable "slack_auth_token_version" {
  type        = string
  description = "Monotonic version for write-only Slack token rotation."
  default     = "1"
}

variable "slack_workspace_id" {
  type        = string
  description = "Slack workspace (team) ID."
  default     = ""
}

variable "slack_channel_incidents" {
  type        = string
  description = "Slack channel for operational incidents."
  default     = "#ops-incidents"
}

variable "slack_channel_security" {
  type        = string
  description = "Slack channel for security findings."
  default     = "#ops-security"
}

variable "slack_channel_finops" {
  type        = string
  description = "Slack channel for FinOps alerts."
  default     = "#ops-finops"
}

variable "slack_channel_platform" {
  type        = string
  description = "Slack channel for platform alerts."
  default     = "#ops-platform"
}

# ---------------------------------------------------------------------------
# Container images
# ---------------------------------------------------------------------------

variable "container_image_action_broker" {
  type        = string
  description = "Container image URI for the action-broker service."
  default     = ""
}

variable "container_image_slack_notifier" {
  type        = string
  description = "Container image URI for the slack-notifier service."
  default     = ""
}

# ---------------------------------------------------------------------------
# Cloud Run sizing
# ---------------------------------------------------------------------------

variable "min_instance_count_broker" {
  type        = number
  description = "Cloud Run min instances for the action-broker. 0 = scale-to-zero (dev); 1+ for prod."
  default     = 0
}

variable "min_instance_count_notifier" {
  type        = number
  description = "Cloud Run min instances for the slack-notifier."
  default     = 0
}

# ---------------------------------------------------------------------------
# Safety / lifecycle
# ---------------------------------------------------------------------------

variable "deletion_policy_prevent" {
  type        = bool
  description = "Set deletion_policy=PREVENT on agent reasoning engines. SHOULD be true in prod."
  default     = false
}

variable "workflows_invoker_resource_pattern" {
  type        = string
  description = "IAM-condition prefix that scopes the action broker's workflows.invoker grant. Empty leaves it project-wide (skeleton)."
  default     = ""
}

variable "labels" {
  type        = map(string)
  description = "Additional labels merged with the canonical AOP label set."
  default     = {}
}
