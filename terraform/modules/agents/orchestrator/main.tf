module "base" {
  source = "../_base"

  project_id              = var.project_id
  region                  = var.region
  env                     = var.env
  agent_slug              = "orchestrator"
  agent_display_name      = "Orchestrator"
  agent_description       = "Ops Orchestrator — deduplicates signals, correlates incidents, routes to specialists, owns the Slack incident thread."
  deletion_policy_prevent = var.deletion_policy_prevent
  enable_memory_bank      = var.enable_memory_bank
  package_pickle_gcs_uri  = var.package_pickle_gcs_uri

  ops_audit_topic_id = var.ops_audit_topic_id
  extra_pubsub_publish_topic_ids = [
    var.ops_notifications_topic_id,
  ]
  extra_pubsub_subscribe_topic_ids = [
    var.ops_signals_topic_id,
  ]

  project_iam_roles = [
    "roles/logging.viewer",
    "roles/monitoring.viewer",
    "roles/datastore.user",
  ]

  schedule = var.schedule
  labels   = var.labels
}
