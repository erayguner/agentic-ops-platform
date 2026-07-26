# Tests for the agent-registry module — MCP server registration, the per-agent
# roles/iap.egressor authorisation matrix, and the two opt-in runtime resources.
# Plan-only; providers are scoped to this test file.

provider "google" {
  project      = "test-project"
  region       = "europe-west2"
  access_token = "fake-token-plan-only-never-used-against-the-api"
}

# File-level defaults; individual runs override what they exercise.
variables {
  project_id = "ops-agents-dev"
  region     = "europe-west2"
  env        = "dev"

  mcp_servers = {
    "logging"    = { url = "https://logging.googleapis.com/mcp" }
    "monitoring" = { url = "https://monitoring.googleapis.com/mcp" }
    "secops"     = { url = "https://chronicle.europe-west2.rep.googleapis.com/mcp" }
  }
}

# ---------------------------------------------------------------------------
# Baseline — registry + IAM only, gateway and policy engine off
# ---------------------------------------------------------------------------

run "agent_registry_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/agent-registry"
  }

  variables {
    agent_grants = {
      devsecops = {
        member      = "serviceAccount:sa-devsecops@ops-agents-dev.iam.gserviceaccount.com"
        mcp_servers = ["logging", "monitoring", "secops"]
      }
      finops = {
        member      = "serviceAccount:sa-finops@ops-agents-dev.iam.gserviceaccount.com"
        mcp_servers = ["monitoring"]
      }
    }
  }

  # The authorisation matrix must be exactly the cartesian product of each
  # agent and its own allow-list — no cross-grants.
  assert {
    condition     = length(output.agent_egress_grants) == 4
    error_message = "Expected 4 (agent, MCP server) grants: 3 for devsecops + 1 for finops."
  }

  assert {
    condition     = alltrue([for k in ["devsecops/logging", "devsecops/monitoring", "devsecops/secops", "finops/monitoring"] : contains(keys(output.agent_egress_grants), k)])
    error_message = "Grant keys must be \"<agent>/<mcp_server>\" for every allow-listed pair."
  }

  # FinOps is monitoring-only — it must not be granted the security surface.
  assert {
    condition     = !contains(keys(output.agent_egress_grants), "finops/secops")
    error_message = "finops must not be granted egress to the SecOps MCP server."
  }

  assert {
    condition     = output.registry_uri == "//agentregistry.googleapis.com/projects/ops-agents-dev/locations/europe-west2"
    error_message = "registry_uri must be the form Agent Gateway expects for its registries list."
  }

  # Both runtime resources default off, so neither should be planned.
  assert {
    condition     = output.agent_gateway_id == null && output.semantic_governance_policy_engine_state == null
    error_message = "Agent Gateway and the policy engine must stay unprovisioned by default."
  }
}

# ---------------------------------------------------------------------------
# Opt-in runtime resources
# ---------------------------------------------------------------------------

run "agent_registry_gateway_and_governance_opt_in" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/agent-registry"
  }

  variables {
    agent_grants = {
      sre = {
        member      = "serviceAccount:sa-sre@ops-agents-dev.iam.gserviceaccount.com"
        mcp_servers = ["logging", "monitoring"]
      }
    }
    enable_agent_gateway       = true
    enable_semantic_governance = true
  }

  assert {
    condition     = google_network_services_agent_gateway.this[0].google_managed[0].governed_access_path == "AGENT_TO_ANYWHERE"
    error_message = "Gateway must default to governing agent egress (AGENT_TO_ANYWHERE)."
  }

  # `protocols` was deprecated in provider 7.37 — assert we never set it, so a
  # future major removing the field cannot break this module.
  assert {
    condition     = try(length(google_network_services_agent_gateway.this[0].protocols), 0) == 0
    error_message = "Gateway must not set the deprecated protocols field."
  }

  assert {
    condition     = contains(google_network_services_agent_gateway.this[0].registries, "//agentregistry.googleapis.com/projects/ops-agents-dev/locations/europe-west2")
    error_message = "Gateway must govern this project's agent registry."
  }

  # No network attachment supplied => no VPC egress block (the managed Google
  # MCP endpoints are public).
  assert {
    condition     = length(google_network_services_agent_gateway.this[0].network_config) == 0
    error_message = "network_config must be omitted unless a network attachment is supplied."
  }
}

# ---------------------------------------------------------------------------
# Location override
# ---------------------------------------------------------------------------

run "agent_registry_location_overrides_region" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/agent-registry"
  }

  variables {
    location     = "us-central1"
    agent_grants = {}
  }

  assert {
    condition     = output.location == "us-central1"
    error_message = "var.location must override var.region for registry placement."
  }
}

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

run "agent_registry_rejects_unqualified_member" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/agent-registry"
  }

  variables {
    agent_grants = {
      sre = {
        member      = "sa-sre@ops-agents-dev.iam.gserviceaccount.com" # missing serviceAccount: prefix
        mcp_servers = ["logging"]
      }
    }
  }

  expect_failures = [var.agent_grants]
}

run "agent_registry_rejects_duplicate_server_grant" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/agent-registry"
  }

  variables {
    agent_grants = {
      sre = {
        member      = "serviceAccount:sa-sre@ops-agents-dev.iam.gserviceaccount.com"
        mcp_servers = ["logging", "logging"]
      }
    }
  }

  expect_failures = [var.agent_grants]
}

run "agent_registry_rejects_invalid_access_path" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/agent-registry"
  }

  variables {
    agent_grants                       = {}
    enable_agent_gateway               = true
    agent_gateway_governed_access_path = "SIDEWAYS"
  }

  expect_failures = [var.agent_gateway_governed_access_path]
}
