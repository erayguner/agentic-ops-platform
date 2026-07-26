output "location" {
  description = "Location the registry, gateway and policy engine were created in."
  value       = local.location
}

output "registry_uri" {
  description = "Registry URI in the form Agent Gateway expects for its `registries` list."
  value       = "//agentregistry.googleapis.com/projects/${var.project_id}/locations/${local.location}"
}

output "mcp_server_ids" {
  description = "Registered MCP server ids, keyed by the var.mcp_servers slug."
  value       = { for k, v in google_agent_registry_service.mcp : k => basename(v.registry_resource) }
}

output "mcp_server_resources" {
  description = "Full registry resource names of the registered MCP servers, keyed by slug."
  value       = { for k, v in google_agent_registry_service.mcp : k => v.registry_resource }
}

output "agent_egress_grants" {
  description = "The (agent, MCP server) pairs granted roles/iap.egressor — useful for asserting the authorisation matrix in tests."
  value       = { for k, v in local.agent_server_grants : k => v.member }
}

output "agent_gateway_id" {
  description = "Agent Gateway resource id, or null when disabled."
  value       = one(google_network_services_agent_gateway.this[*].id)
}

output "agent_gateway_mtls_endpoint" {
  description = "mTLS endpoint agents use to egress through the gateway, or null when disabled."
  # agent_gateway_card is an output-only block; try() keeps this null rather
  # than erroring if the API has not populated it yet.
  value = try(one(google_network_services_agent_gateway.this[*].agent_gateway_card[0].mtls_endpoint), null)
}

output "semantic_governance_policy_engine_state" {
  description = "State of the Semantic Governance Policy Engine (ACTIVE once provisioned), or null when disabled."
  value       = one(google_vertex_ai_semantic_governance_policy_engine.this[*].state)
}
