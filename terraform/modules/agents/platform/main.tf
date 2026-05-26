module "base" {
  source = "../_base"

  project_id              = var.project_id
  region                  = var.region
  env                     = var.env
  agent_slug              = "platform"
  agent_display_name      = "Platform Engineering Agent"
  agent_description       = "Platform Engineering specialist — drift, deployment health, IaC state, resource hygiene, config compliance."
  deletion_policy_prevent = var.deletion_policy_prevent
  package_pickle_gcs_uri  = var.package_pickle_gcs_uri

  ops_audit_topic_id = var.ops_audit_topic_id
  extra_pubsub_publish_topic_ids = [
    var.ops_findings_topic_id,
    var.ops_notifications_topic_id,
  ]

  project_iam_roles = [
    "roles/cloudasset.viewer",
    "roles/resourcemanager.projectViewer",
    "roles/cloudbuild.builds.viewer",
    "roles/clouddeploy.viewer",
  ]

  schedule = var.schedule
  labels   = var.labels
}
