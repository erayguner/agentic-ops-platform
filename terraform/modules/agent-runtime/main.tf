locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "agent-runtime"
      managed_by = "terraform"
    },
    var.labels,
  )

  # DESIGN-REVIEW §5.3: deletion_policy is PREVENT in prod
  deletion_policy = var.deletion_policy_prevent ? "PREVENT" : "DELETE"

  agents = {
    orchestrator = {
      display_name = "AOP Orchestrator (${var.env})"
      description  = "Ops Orchestrator — deduplicates signals, correlates incidents, routes to specialists, owns Slack thread."
      image        = var.container_image_orchestrator
      sa_name      = "sa-orchestrator"
    }
    sre = {
      display_name = "AOP SRE Agent (${var.env})"
      description  = "SRE Agent — reliability, latency, error rate, SLO burn, deploy regressions."
      image        = var.container_image_sre
      sa_name      = "sa-sre"
    }
    devsecops = {
      display_name = "AOP DevSecOps Agent (${var.env})"
      description  = "DevSecOps Agent — SCC findings, IAM drift, key exposure, supply-chain, Model Armor signals."
      image        = var.container_image_devsecops
      sa_name      = "sa-devsecops"
    }
    platform = {
      display_name = "AOP Platform Engineering Agent (${var.env})"
      description  = "Platform Agent — drift, deployment health, IaC state, resource hygiene, config compliance."
      image        = var.container_image_platform
      sa_name      = "sa-platform"
    }
    finops = {
      display_name = "AOP FinOps Agent (${var.env})"
      description  = "FinOps Agent — cost anomalies, budget burn, waste, rightsizing."
      image        = var.container_image_finops
      sa_name      = "sa-finops"
    }
  }
}

# ---------------------------------------------------------------------------
# Service accounts — one per agent.
# ---------------------------------------------------------------------------

resource "google_service_account" "orchestrator" {
  project      = var.project_id
  account_id   = "sa-orchestrator"
  display_name = "AOP Orchestrator agent SA"
  description  = "Identity for the AOP Orchestrator reasoning engine. Read-only; no write IAM on GCP resources."
}

resource "google_service_account" "sre" {
  project      = var.project_id
  account_id   = "sa-sre"
  display_name = "AOP SRE agent SA"
  description  = "Identity for the AOP SRE reasoning engine."
}

resource "google_service_account" "devsecops" {
  project      = var.project_id
  account_id   = "sa-devsecops"
  display_name = "AOP DevSecOps agent SA"
  description  = "Identity for the AOP DevSecOps reasoning engine."
}

resource "google_service_account" "platform" {
  project      = var.project_id
  account_id   = "sa-platform"
  display_name = "AOP Platform Engineering agent SA"
  description  = "Identity for the AOP Platform Engineering reasoning engine."
}

resource "google_service_account" "finops" {
  project      = var.project_id
  account_id   = "sa-finops"
  display_name = "AOP FinOps agent SA"
  description  = "Identity for the AOP FinOps reasoning engine."
}

# ---------------------------------------------------------------------------
# IAM grants — DESIGN-REVIEW §5.3 read-only permissions per agent
# ---------------------------------------------------------------------------

# --- Orchestrator ---
resource "google_project_iam_member" "orchestrator_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_pubsub_topic_iam_member" "orchestrator_signals_subscriber" {
  project = var.project_id
  topic   = var.ops_signals_topic_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_pubsub_topic_iam_member" "orchestrator_notifications_publisher" {
  project = var.project_id
  topic   = var.ops_notifications_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

# --- SRE ---
resource "google_project_iam_member" "sre_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.sre.email}"
}

resource "google_project_iam_member" "sre_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.sre.email}"
}

resource "google_project_iam_member" "sre_cloudtrace_user" {
  project = var.project_id
  role    = "roles/cloudtrace.user"
  member  = "serviceAccount:${google_service_account.sre.email}"
}

resource "google_project_iam_member" "sre_errorreporting_viewer" {
  project = var.project_id
  role    = "roles/errorreporting.viewer"
  member  = "serviceAccount:${google_service_account.sre.email}"
}

resource "google_project_iam_member" "sre_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.sre.email}"
}

resource "google_project_iam_member" "sre_container_viewer" {
  project = var.project_id
  role    = "roles/container.viewer"
  member  = "serviceAccount:${google_service_account.sre.email}"
}

# --- DevSecOps ---
resource "google_project_iam_member" "devsecops_scc_findings_viewer" {
  project = var.project_id
  role    = "roles/securitycenter.findingsViewer"
  member  = "serviceAccount:${google_service_account.devsecops.email}"
}

resource "google_project_iam_member" "devsecops_logging_private_viewer" {
  project = var.project_id
  role    = "roles/logging.privateLogViewer"
  member  = "serviceAccount:${google_service_account.devsecops.email}"
}

resource "google_project_iam_member" "devsecops_iam_security_reviewer" {
  project = var.project_id
  role    = "roles/iam.securityReviewer"
  member  = "serviceAccount:${google_service_account.devsecops.email}"
}

resource "google_project_iam_member" "devsecops_cloudasset_viewer" {
  project = var.project_id
  role    = "roles/cloudasset.viewer"
  member  = "serviceAccount:${google_service_account.devsecops.email}"
}

# --- Platform Engineering ---
resource "google_project_iam_member" "platform_cloudasset_viewer" {
  project = var.project_id
  role    = "roles/cloudasset.viewer"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_resourcemanager_viewer" {
  project = var.project_id
  role    = "roles/resourcemanager.projectViewer"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_cloudbuild_viewer" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.viewer"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

resource "google_project_iam_member" "platform_clouddeploy_viewer" {
  project = var.project_id
  role    = "roles/clouddeploy.viewer"
  member  = "serviceAccount:${google_service_account.platform.email}"
}

# --- FinOps ---
# BigQuery binding for FinOps is dataset-scoped when
# var.billing_export_bq_dataset_id is set, project-wide otherwise. The
# dataset-scoped path is the least-privilege production posture; project-
# wide is the skeleton-friendly fallback.

locals {
  finops_bq_project = (
    var.billing_export_bq_project_id != ""
    ? var.billing_export_bq_project_id
    : var.project_id
  )
  finops_bq_scoped = var.billing_export_bq_dataset_id != ""
}

# Dataset-scoped (preferred): dataViewer ONLY on the billing export dataset.
resource "google_bigquery_dataset_iam_member" "finops_billing_export_viewer" {
  count = local.finops_bq_scoped ? 1 : 0

  project    = local.finops_bq_project
  dataset_id = var.billing_export_bq_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.finops.email}"
}

# Job-level grant (jobUser): needed to RUN queries; cannot be scoped finer
# than project. Only created when the dataset-scoped binding is used.
resource "google_project_iam_member" "finops_bigquery_job_user" {
  count = local.finops_bq_scoped ? 1 : 0

  project = local.finops_bq_project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.finops.email}"
}

# Fallback (project-wide) — only when no billing dataset is named. Wider
# than necessary; flagged in docs/GOVERNANCE-MAPPING.md as a known gap.
resource "google_project_iam_member" "finops_bigquery_data_viewer_project_wide" {
  count = local.finops_bq_scoped ? 0 : 1

  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.finops.email}"
}

resource "google_project_iam_member" "finops_recommender_viewer" {
  project = var.project_id
  role    = "roles/recommender.viewer"
  member  = "serviceAccount:${google_service_account.finops.email}"
}

# ---------------------------------------------------------------------------
# Pub/Sub publisher bindings — producer matrix.
#
# Specialists publish Finding v1 → ops.findings.
# Every agent (orchestrator + specialists) publishes:
#   OpsNotification → ops.notifications  (via aop_common.slack_emitter)
#   AuditRecord     → ops.audit          (via aop_common.audit)
#
# Bindings are emitted per-(SA × topic) so the IAM surface mirrors the
# schema fanout exactly. The orchestrator's ops.notifications binding is
# created above in the orchestrator block; specialist bindings live here
# to keep the per-SA grants discoverable as one group.
# ---------------------------------------------------------------------------

locals {
  specialist_sa_emails = {
    sre       = google_service_account.sre.email
    devsecops = google_service_account.devsecops.email
    platform  = google_service_account.platform.email
    finops    = google_service_account.finops.email
  }
  all_agent_sa_emails = merge(
    { orchestrator = google_service_account.orchestrator.email },
    local.specialist_sa_emails,
  )
}

# Specialists → ops.findings (Finding v1 producer).
resource "google_pubsub_topic_iam_member" "specialist_findings_publisher" {
  for_each = local.specialist_sa_emails

  project = var.project_id
  topic   = var.ops_findings_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${each.value}"
}

# Specialists → ops.notifications (OpsNotification producer via SlackEmitter).
# Orchestrator already has this grant above.
resource "google_pubsub_topic_iam_member" "specialist_notifications_publisher" {
  for_each = local.specialist_sa_emails

  project = var.project_id
  topic   = var.ops_notifications_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${each.value}"
}

# All agents → ops.audit (AuditRecord producer via AuditEmitter).
resource "google_pubsub_topic_iam_member" "all_agents_audit_publisher" {
  for_each = local.all_agent_sa_emails

  project = var.project_id
  topic   = var.ops_audit_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${each.value}"
}

# ---------------------------------------------------------------------------
# Reasoning Engines (Agent Engine deployments) — one per agent
# ---------------------------------------------------------------------------

# --- Orchestrator ---
resource "google_vertex_ai_reasoning_engine" "orchestrator" {
  project      = var.project_id
  region       = var.region
  display_name = local.agents.orchestrator.display_name
  description  = local.agents.orchestrator.description

  spec {
    agent_framework = "google-adk"
    package_spec {
      python_version = "3.12"
      # Actual package URI set at deploy time via CI. Placeholder here.
      pickle_object_gcs_uri = "gs://REPLACE_BUCKET/orchestrator/agent.pkl"
    }
  }

  deletion_policy = local.deletion_policy
}

# --- SRE Agent ---
resource "google_vertex_ai_reasoning_engine" "sre" {
  project      = var.project_id
  region       = var.region
  display_name = local.agents.sre.display_name
  description  = local.agents.sre.description

  spec {
    agent_framework = "google-adk"
    package_spec {
      python_version        = "3.12"
      pickle_object_gcs_uri = "gs://REPLACE_BUCKET/sre/agent.pkl"
    }
  }

  deletion_policy = local.deletion_policy
}

# --- DevSecOps Agent ---
resource "google_vertex_ai_reasoning_engine" "devsecops" {
  project      = var.project_id
  region       = var.region
  display_name = local.agents.devsecops.display_name
  description  = local.agents.devsecops.description

  spec {
    agent_framework = "google-adk"
    package_spec {
      python_version        = "3.12"
      pickle_object_gcs_uri = "gs://REPLACE_BUCKET/devsecops/agent.pkl"
    }
  }

  deletion_policy = local.deletion_policy
}

# --- Platform Engineering Agent ---
resource "google_vertex_ai_reasoning_engine" "platform" {
  project      = var.project_id
  region       = var.region
  display_name = local.agents.platform.display_name
  description  = local.agents.platform.description

  spec {
    agent_framework = "google-adk"
    package_spec {
      python_version        = "3.12"
      pickle_object_gcs_uri = "gs://REPLACE_BUCKET/platform/agent.pkl"
    }
  }

  deletion_policy = local.deletion_policy
}

# --- FinOps Agent ---
resource "google_vertex_ai_reasoning_engine" "finops" {
  project      = var.project_id
  region       = var.region
  display_name = local.agents.finops.display_name
  description  = local.agents.finops.description

  spec {
    agent_framework = "google-adk"
    package_spec {
      python_version        = "3.12"
      pickle_object_gcs_uri = "gs://REPLACE_BUCKET/finops/agent.pkl"
    }
  }

  deletion_policy = local.deletion_policy
}

# ---------------------------------------------------------------------------
# Memory Bank (context_spec) — requires google-beta provider
# context_spec.memory_bank_config is only available in the beta API surface.
# TODO: remove provider=google-beta once context_spec graduates to GA
#       in hashicorp/google (track upstream issue:
#       https://github.com/hashicorp/terraform-provider-google/issues/XXXXX).
# ---------------------------------------------------------------------------

resource "google_vertex_ai_reasoning_engine" "orchestrator_memory" {
  provider     = google-beta # BETA: context_spec.memory_bank_config is not in the GA provider
  project      = var.project_id
  region       = var.region
  display_name = "AOP Orchestrator — Memory Bank (${var.env})"
  description  = "Memory Bank configuration for the Orchestrator agent. Separate resource due to beta provider requirement."

  spec {
    agent_framework = "google-adk"
    package_spec {
      python_version        = "3.12"
      pickle_object_gcs_uri = "gs://REPLACE_BUCKET/orchestrator/agent.pkl"
    }
  }

  context_spec {
    memory_bank_config {}
  }

  deletion_policy = local.deletion_policy
}
