# All five agents, all platform layers — useful for a freshly-bootstrapped
# sandbox project where you want to exercise every path. Defaults match the
# scaffold's existing dev posture (scale-to-zero, deletion allowed, etc.).

module "aop" {
  source = "../../modules/aop-platform"

  project_id = var.project_id
  region     = var.region
  env        = "dev"

  essential_contacts_email = var.essential_contacts_email
  slack_auth_token         = var.slack_auth_token
  slack_workspace_id       = var.slack_workspace_id

  enabled_agents = {
    orchestrator = {}
    sre          = {}
    devsecops    = {}
    platform     = {}
    finops       = {}
  }
}
