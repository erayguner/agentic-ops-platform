# Minimal posture — only the SRE agent, plus the bare-minimum platform layers
# it needs. No action broker, no Slack notifier. Useful for read-only SRE
# investigation pipelines or for a team that wants to dip into AOP without
# adopting the full surface area.

module "aop" {
  source = "../../modules/aop-platform"

  project_id = var.project_id
  region     = var.region
  env        = "dev"

  essential_contacts_email = var.essential_contacts_email

  # Disable layers we do not need.
  enable_action_broker  = false
  enable_slack_notifier = false
  enable_observability  = false # turn back on once you have a Slack channel
  enable_governance     = true  # keeps Model Armor / SCC notification active

  enabled_agents = {
    sre = {
      schedule = {
        cron       = "*/15 * * * *"
        target_uri = "https://sre-agent-fanout.example.com/sweep"
      }
    }
  }
}

output "sre_sa_email" {
  value = module.aop.agent_sa_emails["sre"]
}

output "sre_reasoning_engine_id" {
  value = module.aop.agent_reasoning_engine_ids["sre"]
}

output "sre_schedule_job_id" {
  value = module.aop.agent_scheduler_job_ids["sre"]
}
