locals {
  bq_scoped     = var.billing_export_bq_dataset_id != ""
  bq_project_id = var.billing_export_bq_project_id != "" ? var.billing_export_bq_project_id : var.project_id

  # Predefined project-scoped roles. The bigquery.jobUser binding is only
  # present when a dataset is named (dataset-scoped path), and the
  # project-wide dataViewer is the fallback when no dataset is named.
  predefined_roles = concat(
    [
      "roles/recommender.viewer",
    ],
    local.bq_scoped ? ["roles/bigquery.jobUser"] : ["roles/bigquery.dataViewer"],
  )
}

module "base" {
  source = "../_base"

  project_id              = var.project_id
  region                  = var.region
  env                     = var.env
  agent_slug              = "finops"
  agent_display_name      = "FinOps Agent"
  agent_description       = "FinOps specialist — cost anomalies, budget burn, waste, rightsizing."
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

# Dataset-scoped bigquery.dataViewer (preferred posture). When
# billing_export_bq_dataset_id is set, this binding gives the FinOps SA
# read access ONLY to the billing export dataset, not the entire project.
resource "google_bigquery_dataset_iam_member" "billing_export_viewer" {
  count = local.bq_scoped ? 1 : 0

  project    = local.bq_project_id
  dataset_id = var.billing_export_bq_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = module.base.sa_member
}

check "billing_export_dataset_scoped_in_prod" {
  assert {
    condition     = var.env != "prod" || local.bq_scoped
    error_message = "FinOps in prod must set billing_export_bq_dataset_id; project-wide bigquery.dataViewer is too broad for production."
  }
}
