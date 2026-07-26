# module/agent-registry

Turns the agents' MCP allow-list from an application convention into an enforced authorisation boundary.

## Why

Agents reach managed Google MCP servers as bare URLs — the constants in `agents/aop_common/mcp_tools.py` — authenticated with an ADC bearer token. The per-agent allow-lists live only in Python, so nothing outside the agent process enforces them: any agent whose code dialled an endpoint would be served, provided its service account held the underlying viewer role. The allow-list documents intent; it does not constrain.

Registering each MCP server here makes the boundary real. IAP grants `roles/iap.egressor` per `(agent, server)` pair, so the authorisation matrix is expressed in IAM — auditable in one place and enforced independently of the agent code.

This module **authorises**; it does not configure the agents. The Python allow-lists still decide which toolsets an agent builds. Keep the two in step: an endpoint registered here but absent from the Python list is merely unused, whereas the reverse means an agent calls an endpoint that Agent Gateway does not govern.

## Resources created

- **`google_agent_registry_service`** — one per entry in `var.mcp_servers`, declared as an MCP Server (`mcp_server_spec`) with a `JSONRPC` interface, matching the streamable-HTTP transport `aop_common.mcp_tools` binds.
- **`google_iap_agent_registry_mcp_server_iam_member`** — one per `(agent, server)` pair, granting `roles/iap.egressor`. Non-authoritative `_member` resources, so adding an agent never rewrites another's access.
- **`google_network_services_agent_gateway`** *(opt-in)* — Google-managed gateway governing agent egress to the registered servers.
- **`google_vertex_ai_semantic_governance_policy_engine`** *(opt-in)* — the runtime decision point the gateway consults to allow or deny a proposed tool call.

## Usage

```hcl
module "agent_registry" {
  source = "../agent-registry"

  project_id = "ops-agents-dev"
  region     = "europe-west2"
  env        = "dev"

  mcp_servers = {
    "logging"    = { url = "https://logging.googleapis.com/mcp" }
    "monitoring" = { url = "https://monitoring.googleapis.com/mcp" }
  }

  agent_grants = {
    sre = {
      member      = module.agent_sre.sa_member
      mcp_servers = ["logging", "monitoring"]
    }
  }
}
```

`aop-platform` wires this automatically from its own catalogue and the enabled agents' service accounts — see `enable_agent_registry`.

## Inputs

| Name                               | Type        | Default             | Required |
| ---------------------------------- | ----------- | ------------------- | -------- |
| project_id                         | string      | —                   | yes      |
| region                             | string      | —                   | yes      |
| env                                | string      | —                   | yes      |
| location                           | string      | `null` (→ region)   | no       |
| mcp_servers                        | map(object) | `{}`                | no       |
| agent_grants                       | map(object) | `{}`                | no       |
| enable_agent_gateway               | bool        | `false`             | no       |
| agent_gateway_governed_access_path | string      | `AGENT_TO_ANYWHERE` | no       |
| agent_gateway_network_attachment   | string      | `null`              | no       |
| enable_semantic_governance         | bool        | `false`             | no       |
| deletion_policy                    | string      | `DELETE`            | no       |
| labels                             | map(string) | `{}`                | no       |

## Outputs

| Name                                     | Description                                              |
| ---------------------------------------- | -------------------------------------------------------- |
| location                                 | Location the resources were created in.                   |
| registry_uri                             | Registry URI in the form Agent Gateway expects.           |
| mcp_server_ids                           | Registered MCP server ids, keyed by slug.                 |
| mcp_server_resources                     | Full registry resource names, keyed by slug.              |
| agent_egress_grants                      | The `(agent/server) => member` authorisation matrix.      |
| agent_gateway_id                         | Gateway id, or `null` when disabled.                      |
| agent_gateway_mtls_endpoint              | Gateway mTLS endpoint, or `null` when disabled.           |
| semantic_governance_policy_engine_state  | Engine state (`ACTIVE` once provisioned), or `null`.      |

## Operational notes

- **Regional availability.** Agent Registry is a young API with narrower coverage than the rest of the platform. If an apply reports the region as unsupported, set `var.location` rather than moving `var.region`, which would relocate everything.
- **The opt-in resources are slow.** Agent Gateway takes up to 30 minutes to provision and the policy engine up to 60, and the engine allocates managed Private Service Connect networking in the VPC. Both default to off; enabling the gateway does not by itself reroute any agent.
- **Policies are configured elsewhere.** The policy engine is the evaluation infrastructure; the semantic governance policies it evaluates are not managed by this resource.
- **Renaming a key is destructive.** `var.mcp_servers` keys become `service_id`s — changing one destroys and recreates the registry entry along with every IAM binding attached to it.
- **`protocols` is deliberately unset** on the gateway: deprecated in provider 7.37 and slated for removal. The mode is expressed through `google_managed.governed_access_path`, and a test asserts we never set it.
