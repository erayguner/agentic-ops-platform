module "base" {
  source = "../_base"

  project_id              = var.project_id
  region                  = var.region
  env                     = var.env
  agent_slug              = "sre"
  agent_display_name      = "SRE Agent"
  agent_description       = "SRE specialist — reliability, latency, error rate, SLO burn, deploy regressions. Produces Finding v1 with cause hypothesis."
  deletion_policy_prevent = var.deletion_policy_prevent
  package_pickle_gcs_uri  = var.package_pickle_gcs_uri

  ops_audit_topic_id = var.ops_audit_topic_id
  extra_pubsub_publish_topics = {
    findings      = var.ops_findings_topic_id
    notifications = var.ops_notifications_topic_id
  }

  project_iam_roles = [
    "roles/logging.viewer",
    "roles/monitoring.viewer",
    "roles/cloudtrace.user",
    "roles/errorreporting.viewer",
    "roles/run.viewer",
    "roles/container.viewer",
  ]

  schedule = var.schedule
  labels   = var.labels
}
