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
  extra_pubsub_publish_topics = {
    findings      = var.ops_findings_topic_id
    notifications = var.ops_notifications_topic_id
  }

  project_iam_roles = [
    "roles/securitycenter.findingsViewer",
    "roles/logging.privateLogViewer",
    "roles/iam.securityReviewer",
    "roles/cloudasset.viewer",
    # Read-only SecOps/Chronicle access. The DevSecOps prompt directs the agent
    # to query Chronicle MCP for related alerts/IOCs first, and
    # SECOPS_MCP_TEMPLATE is in DEVSECOPS_MCP_ENDPOINTS; without this role that
    # call 403s. Viewer only — response actions go through the Action Broker.
    "roles/chronicle.viewer",
  ]

  schedule = var.schedule
  labels   = var.labels
}
