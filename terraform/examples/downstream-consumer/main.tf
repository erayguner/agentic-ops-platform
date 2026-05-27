# Consume the AOP framework from another repository.
#
# In this in-repo example the `source` is a local relative path so the
# example stays validate-ready in CI. When you copy this file into your own
# downstream repository, swap the source for the git URL form (see README):
#
#   source = "git::https://github.com/erayguner/agentic-ops-platform.git//terraform/modules/aop-platform?ref=v0.1.0"
#
# Terraform requires `source` to be a string literal — bumping the version is
# a one-line edit. The `aop_framework_version` variable below is exposed only
# so dashboards/inventories can read which version is in use.
#
# Remember to run `./scripts/preflight.sh` (vendored or pulled from the AOP
# repo) before plan/apply.

module "aop" {
  source = "../../modules/aop-platform"

  project_id = var.project_id
  region     = var.region
  env        = var.env

  essential_contacts_email = var.essential_contacts_email
  slack_auth_token         = var.slack_auth_token
  slack_workspace_id       = var.slack_workspace_id

  enabled_agents = {
    sre       = {}
    devsecops = {}
  }

  labels = {
    consumer = "downstream-app"
  }
}

# Downstream-side IAM — give an app SA permission to subscribe to ops.findings.
# This stays in the consumer repo because the framework cannot know which
# downstream identities exist.
resource "google_pubsub_topic_iam_member" "downstream_findings_subscriber" {
  count = length(module.aop.topic_ids) == 0 ? 0 : 1

  project = var.project_id
  topic   = module.aop.topic_ids.ops_findings
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:downstream-app@${var.project_id}.iam.gserviceaccount.com"
}
