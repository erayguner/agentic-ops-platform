# Staging posture — production-like settings, but with deletion still allowed
# (so the env can be reset) and warm Cloud Run pools to surface cold-start
# issues before prod.

module "aop" {
  source = "../../modules/aop-platform"

  project_id = var.project_id
  region     = var.region
  env        = "staging"

  essential_contacts_email = var.essential_contacts_email
  slack_auth_token         = var.slack_auth_token
  slack_workspace_id       = var.slack_workspace_id

  finops_billing_export_bq_dataset_id = var.finops_billing_export_bq_dataset_id

  # Production-like sizing
  min_instance_count_broker   = 1
  min_instance_count_notifier = 1

  # Staging keeps destroy enabled so the env can be torn down deliberately.
  deletion_policy_prevent = false

  enabled_agents = {
    orchestrator = {}
    sre          = {}
    devsecops    = {}
    platform     = {}
    finops = {
      schedule = {
        cron       = "0 6 * * *"
        target_uri = "https://finops-fan-out-staging.example.com/run"
      }
    }
  }

  labels = {
    cost_centre = "platform-staging"
  }
}
