variable "project_id" {
  type        = string
  description = "GCP project that owns the Agent Registry."
}

variable "region" {
  type        = string
  description = "Default region. Used for the registry location unless var.location overrides it."
}

variable "location" {
  type        = string
  description = <<-EOT
    Location for the Agent Registry services, Agent Gateway and policy engine.
    Defaults to var.region when null.

    Agent Registry is a young API and is not available in every region — if an
    apply fails with a location error, pin this to a supported region (the
    upstream examples use us-central1) rather than changing var.region, which
    would move the whole platform.
  EOT
  default     = null
}

variable "env" {
  type        = string
  description = "Environment slug (dev/staging/prod)."
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}

variable "mcp_servers" {
  type = map(object({
    url          = string
    display_name = optional(string)
    description  = optional(string)
  }))
  description = <<-EOT
    Managed MCP servers to register, keyed by short slug (e.g. "logging").

    The key becomes the service_id, so it must be a stable, DNS-ish identifier —
    renaming a key destroys and recreates the registry entry and every IAM
    binding attached to it.

    These mirror the endpoint constants in agents/aop_common/mcp_tools.py, which
    remains the source of truth for what an agent actually connects to. This map
    governs *authorisation* for those endpoints; it does not configure the
    agents. Keep the two in step — an endpoint registered here but absent from
    the Python allow-list is simply unused, while the reverse means the agent
    calls an endpoint that Agent Gateway does not govern.
  EOT
  default     = {}
}

variable "agent_grants" {
  type = map(object({
    member      = string
    mcp_servers = list(string)
  }))
  description = <<-EOT
    Per-agent authorisation, keyed by agent slug (e.g. "devsecops").

    `member` is an IAM member string (the agent's service account, as
    "serviceAccount:..."), and `mcp_servers` lists keys from var.mcp_servers
    that the agent may reach. Each pair becomes a
    google_iap_agent_registry_mcp_server_iam_member granting roles/iap.egressor
    on exactly that server — replacing the previous model where every agent
    could reach any endpoint its process happened to dial.

    Every entry in `mcp_servers` must exist in var.mcp_servers; a typo would
    otherwise silently grant nothing, so it is validated below.
  EOT
  default     = {}

  validation {
    condition = alltrue([
      for grant in values(var.agent_grants) : length(grant.mcp_servers) == length(distinct(grant.mcp_servers))
    ])
    error_message = "agent_grants[*].mcp_servers must not contain duplicate entries."
  }

  validation {
    condition = alltrue([
      for grant in values(var.agent_grants) : startswith(grant.member, "serviceAccount:") || startswith(grant.member, "group:") || startswith(grant.member, "user:")
    ])
    error_message = "agent_grants[*].member must be a qualified IAM member (serviceAccount:, group: or user:)."
  }
}

variable "enable_agent_gateway" {
  type        = bool
  description = <<-EOT
    Provision a Google-managed Agent Gateway in front of the registry.

    Off by default: the gateway sits in the agent traffic path, takes up to 30
    minutes to provision, and only does useful work once agents are configured
    to egress through it. Turning it on does not by itself reroute any agent.
  EOT
  default     = false
}

variable "agent_gateway_governed_access_path" {
  type        = string
  description = <<-EOT
    Agent Gateway operating mode.

    AGENT_TO_ANYWHERE governs traffic *from* the platform's agents out to MCP
    servers and other services — the direction this platform cares about.
    CLIENT_TO_AGENT governs inbound traffic to agents instead.
  EOT
  default     = "AGENT_TO_ANYWHERE"

  validation {
    condition     = contains(["AGENT_TO_ANYWHERE", "CLIENT_TO_AGENT"], var.agent_gateway_governed_access_path)
    error_message = "agent_gateway_governed_access_path must be AGENT_TO_ANYWHERE or CLIENT_TO_AGENT."
  }
}

variable "agent_gateway_network_attachment" {
  type        = string
  description = <<-EOT
    Optional PSC network-attachment URI giving the gateway egress into the AOP
    VPC (google_compute_network_attachment.id).

    Only needed to reach private destinations. The managed Google MCP endpoints
    are public, so this stays null for the default deployment.
  EOT
  default     = null
}

variable "enable_semantic_governance" {
  type        = bool
  description = <<-EOT
    Provision the Vertex AI Semantic Governance Policy Engine — the runtime
    decision point that evaluates natural-language policy against an agent's
    proposed tool calls, which Agent Gateway consults.

    Off by default and deliberately separate from var.enable_agent_gateway: it
    is a project/region singleton, takes up to 60 minutes to provision, and
    allocates managed Private Service Connect networking in the VPC. The
    policies themselves are configured outside Terraform — this resource only
    provisions the engine that evaluates them.
  EOT
  default     = false
}

variable "deletion_policy" {
  type        = string
  description = "deletion_policy for registry services and the policy engine (DELETE, ABANDON or PREVENT)."
  default     = "DELETE"

  validation {
    condition     = contains(["DELETE", "ABANDON", "PREVENT"], var.deletion_policy)
    error_message = "deletion_policy must be one of DELETE, ABANDON, PREVENT."
  }
}
