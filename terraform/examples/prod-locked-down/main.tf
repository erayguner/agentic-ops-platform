# Production posture. The composition module's check blocks enforce the
# production invariants — this example simply provides production values.

module "aop" {
  source = "../../modules/aop-platform"

  project_id = var.project_id
  region     = var.region
  env        = "prod"

  essential_contacts_email = var.essential_contacts_email
  slack_auth_token         = var.slack_auth_token
  slack_auth_token_version = var.slack_auth_token_version
  slack_workspace_id       = var.slack_workspace_id

  container_image_action_broker  = var.container_image_action_broker
  container_image_slack_notifier = var.container_image_slack_notifier

  finops_billing_export_bq_dataset_id = var.finops_billing_export_bq_dataset_id
  finops_billing_export_bq_project_id = var.finops_billing_export_bq_project_id

  # Warm pools + deletion lock.
  min_instance_count_broker          = 1
  min_instance_count_notifier        = 1
  deletion_policy_prevent            = true
  workflows_invoker_resource_pattern = var.workflows_invoker_resource_pattern

  enabled_agents = {
    orchestrator = { enable_memory_bank = true }
    sre          = {}
    devsecops    = {}
    platform     = {}
    finops = {
      schedule = {
        cron       = "0 6 * * *"
        target_uri = "https://finops-fan-out-prod.example.com/run"
      }
    }
  }

  labels = {
    cost_centre = "platform-prod"
    pii_scope   = "none"
  }
}
