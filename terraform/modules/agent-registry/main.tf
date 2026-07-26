# Agent Registry — authorisation layer for the MCP servers the agents consume.
#
# Why: agents previously reached MCP endpoints as bare URLs (the constants in
# aop_common/mcp_tools.py) carrying an ADC bearer token. The allow-list lived
# only in Python, so it was an application-level convention, not an enforced
# boundary: any agent whose code dialled an endpoint would be served by it as
# long as its service account held the underlying viewer role.
#
# Registering each MCP server here makes that boundary real. IAP grants
# roles/iap.egressor per (agent, server) pair, so authorisation is expressed in
# IAM and auditable in one place, and Agent Gateway (optional, below) can
# govern the traffic centrally.
#
# Layering: this module authorises; it does not configure the agents. The
# Python allow-lists still determine which toolsets an agent builds.

locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "agent-registry"
      managed_by = "terraform"
    },
    var.labels,
  )

  location = coalesce(var.location, var.region)

  # Cartesian product of agents x their permitted MCP servers, keyed
  # "<agent>/<server>" so for_each addresses stay stable when either list
  # changes. merge(...)... collapses the per-agent maps into one flat map;
  # the empty map keeps merge() valid when there are no grants at all.
  agent_server_grants = merge(
    {},
    [
      for agent_slug, grant in var.agent_grants : {
        for server_key in grant.mcp_servers :
        "${agent_slug}/${server_key}" => {
          agent_slug = agent_slug
          member     = grant.member
          server_key = server_key
        }
      }
    ]...
  )
}

# ---------------------------------------------------------------------------
# Registered MCP servers
# ---------------------------------------------------------------------------

resource "google_agent_registry_service" "mcp" {
  for_each = var.mcp_servers

  project    = var.project_id
  location   = local.location
  service_id = each.key

  display_name = coalesce(each.value.display_name, each.key)
  description  = coalesce(each.value.description, "AOP-consumed managed MCP server: ${each.key}")

  interfaces {
    url = each.value.url
    # The managed Google MCP servers speak JSON-RPC over streamable HTTP, which
    # is what aop_common.mcp_tools binds via StreamableHTTPConnectionParams.
    protocol_binding = "JSONRPC"
  }

  # Declaring the service as an MCP Server (rather than Agent or Endpoint) is
  # what makes the IAP AgentRegistryMcpServer IAM surface below applicable.
  # NO_SPEC: these are Google-managed servers whose tool schemas we consume
  # rather than declare. Supplying a TOOL_SPEC would assert a tool list we do
  # not own and would drift as Google changes it.
  mcp_server_spec {
    type = "NO_SPEC"
  }

  deletion_policy = var.deletion_policy
}

# ---------------------------------------------------------------------------
# Per-agent egress authorisation
# ---------------------------------------------------------------------------

# Non-authoritative _member (not _binding): each grant owns exactly its own
# (server, role, member) tuple, so adding an agent never rewrites another
# agent's access, and anything granted out-of-band is left untouched rather
# than silently revoked on the next apply.
resource "google_iap_agent_registry_mcp_server_iam_member" "agent_egress" {
  for_each = local.agent_server_grants

  project  = var.project_id
  location = local.location

  # registry_resource is the full resource name of the MCP Server the service
  # produced (projects/*/locations/*/mcpServers/<id>); IAP addresses it by bare
  # id. Reading it back from the API response rather than assuming it equals
  # service_id keeps this correct if the registry ever derives ids differently.
  mcp_server_id = basename(google_agent_registry_service.mcp[each.value.server_key].registry_resource)

  role   = "roles/iap.egressor"
  member = each.value.member

  lifecycle {
    precondition {
      condition     = contains(keys(var.mcp_servers), each.value.server_key)
      error_message = "agent_grants[\"${each.value.agent_slug}\"] references MCP server \"${each.value.server_key}\", which is not a key in var.mcp_servers."
    }
  }
}

# ---------------------------------------------------------------------------
# Agent Gateway (opt-in) — governs agent egress through the registry
# ---------------------------------------------------------------------------

resource "google_network_services_agent_gateway" "this" {
  count = var.enable_agent_gateway ? 1 : 0

  project     = var.project_id
  name        = "aop-${var.env}-agent-gateway"
  location    = local.location
  description = "AOP ${var.env} — governs agent egress to registered MCP servers"

  # `protocols` is deliberately unset: deprecated in provider 7.37 and slated
  # for removal in the next major. Mode is expressed by google_managed below.
  google_managed {
    governed_access_path = var.agent_gateway_governed_access_path
  }

  registries = [
    "//agentregistry.googleapis.com/projects/${var.project_id}/locations/${local.location}",
  ]

  # Only emitted when a network attachment is supplied — the managed Google MCP
  # endpoints are public, so the default deployment needs no VPC path and an
  # empty egress block would be rejected.
  dynamic "network_config" {
    for_each = var.agent_gateway_network_attachment == null ? [] : [var.agent_gateway_network_attachment]
    content {
      egress {
        network_attachment = network_config.value
      }
    }
  }

  labels = local.common_labels

  # The gateway resolves `registries` at create time, so the registered servers
  # must exist first.
  depends_on = [google_agent_registry_service.mcp]
}

# ---------------------------------------------------------------------------
# Semantic Governance Policy Engine (opt-in)
# ---------------------------------------------------------------------------

# Project/region singleton — the runtime decision point Agent Gateway consults
# to allow or deny a proposed tool call. The policies it evaluates are managed
# outside Terraform; this only provisions the engine.
resource "google_vertex_ai_semantic_governance_policy_engine" "this" {
  count = var.enable_semantic_governance ? 1 : 0

  project = var.project_id
  region  = local.location

  deletion_policy = var.deletion_policy
}
