module "base" {
  source = "../_base"

  project_id              = var.project_id
  region                  = var.region
  env                     = var.env
  agent_slug              = "devsecops"
  agent_display_name      = "DevSecOps Agent"
  agent_description       = "DevSecOps specialist — SCC findings, IAM drift, key exposure, supply-chain signals, Model Armor alerts."
  deletion_policy_prevent = var.deletion_policy_prevent
  package_pickle_gcs_uri  = var.package_pickle_gcs_uri

  ops_audit_topic_id = var.ops_audit_topic_id
  extra_pubsub_publish_topic_ids = [
    var.ops_findings_topic_id,
    var.ops_notifications_topic_id,
  ]

  project_iam_roles = [
    "roles/securitycenter.findingsViewer",
    "roles/logging.privateLogViewer",
    "roles/iam.securityReviewer",
    "roles/cloudasset.viewer",
  ]

  schedule = var.schedule
  labels   = var.labels
}
