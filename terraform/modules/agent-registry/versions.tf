terraform {
  required_version = ">= 1.10"
  required_providers {
    google = {
      source = "hashicorp/google"
      # google_agent_registry_service and the IAP AgentRegistry IAM resources
      # landed in 7.39; the granular per-MCP-server IAM used here is 7.40.
      version = "~> 7.40"
    }
  }
}
