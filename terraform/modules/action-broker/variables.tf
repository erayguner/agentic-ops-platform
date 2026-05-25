variable "project_id" {
  type        = string
  description = "GCP project ID where action-broker resources are created."
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
  description = "GCP region for the Cloud Run service."
  default     = "europe-west2"
}

variable "container_image" {
  type        = string
  description = "Container image URI for the action-broker service."
  default     = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/action-broker:latest"
}

variable "ops_actions_approved_topic_id" {
  type        = string
  description = "Resource ID of the ops.actions.approved Pub/Sub topic (broker subscribes to this)."
}

variable "ops_actions_requested_topic_id" {
  type        = string
  description = "Resource ID of the ops.actions.requested Pub/Sub topic (broker publishes to this)."
}

variable "ops_actions_executed_topic_id" {
  type        = string
  description = "Resource ID of the ops.actions.executed Pub/Sub topic (broker publishes outcomes)."
}

variable "ops_audit_topic_id" {
  type        = string
  description = "Resource ID of the ops.audit Pub/Sub topic (broker emits audit records)."
}

variable "min_instance_count" {
  type        = number
  description = "Minimum Cloud Run instances (0 = scale-to-zero in dev)."
  default     = 0
}

variable "max_instance_count" {
  type        = number
  description = "Maximum Cloud Run instances."
  default     = 3
}

variable "agent_sa_emails" {
  type        = list(string)
  description = <<-EOT
    Service account emails of agent reasoning engines that need run.invoker
    on the action-broker (so propose_action MCP calls resolve). Empty by
    default — the broker is only callable by itself until the env root wires
    in the agent SAs after agent_runtime applies. Adding an SA here is the
    only IAM-level way to grant a caller; ingress + authentication are
    enforced separately.
  EOT
  default     = []
}

variable "workflows_invoker_resource_pattern" {
  type        = string
  description = <<-EOT
    Workflow-name pattern (string-prefix match) used as an IAM condition on
    the workflows.invoker role granted to sa-action-workflows-run. When set,
    the SA can only invoke workflows whose resource name begins with
    `projects/<project>/locations/<region>/workflows/<pattern>`. Empty (the
    default) preserves the project-wide grant for skeleton flexibility;
    production deployments SHOULD set this (e.g. `aop-` for AOP-managed
    workflows) to scope the blast radius of workflows.run.
  EOT
  default     = ""
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
