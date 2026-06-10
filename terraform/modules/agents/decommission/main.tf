locals {
  # Read-only discovery roles only. The decommission agent inventories the
  # estate (Asset Inventory + Resource Manager), reads activity/idle signals
  # (Monitoring, Logging, Recommender), and proposes every teardown through the
  # Action Broker. It holds NO delete/write IAM — that is the whole point of the
  # decision/execution split, and it matters most for the one agent whose job is
  # destruction.
  predefined_roles = [
    "roles/cloudasset.viewer",
    "roles/resourcemanager.projectViewer",
    "roles/monitoring.viewer",
    "roles/logging.viewer",
    "roles/recommender.viewer",
  ]
}

module "base" {
  source = "../_base"

  project_id              = var.project_id
  region                  = var.region
  env                     = var.env
  agent_slug              = "decommission"
  agent_display_name      = "Decommission Agent"
  agent_description       = "Project-closure specialist — inventory, exemption-aware teardown planning, Broker-gated destroys, closure validation."
  deletion_policy_prevent = var.deletion_policy_prevent
  package_pickle_gcs_uri  = var.package_pickle_gcs_uri

  ops_audit_topic_id = var.ops_audit_topic_id
  extra_pubsub_publish_topics = {
    findings      = var.ops_findings_topic_id
    notifications = var.ops_notifications_topic_id
  }

  project_iam_roles = local.predefined_roles

  schedule = var.schedule
  labels   = var.labels
}

# Belt-and-braces: the SA for the one agent whose mandate is destruction must
# never hold a mutating role. _base already refuses owner/editor; this asserts
# the stronger "read-only only" invariant for this module specifically.
check "decommission_sa_is_read_only" {
  assert {
    condition = alltrue([
      for r in local.predefined_roles :
      can(regex("(?i)(viewer|reader|browser)$", r)) &&
      !can(regex("(?i)(admin|editor|owner|writer|delete|destroy)", r))
    ])
    error_message = "Decommission agent SA must hold only read-only roles; all destroys go through the Action Broker."
  }
}
