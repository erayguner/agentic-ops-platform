locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "action-broker"
      managed_by = "terraform"
    },
    var.labels,
  )
}

# ---------------------------------------------------------------------------
# Service account — sa-action-broker (the ONLY SA that impersonates action SAs)
# ---------------------------------------------------------------------------

resource "google_service_account" "action_broker" {
  project      = var.project_id
  account_id   = "sa-action-broker"
  display_name = "AOP Action Broker SA"
  description  = "Identity for the action-broker Cloud Run service. Holds no broad write IAM; only iam.serviceAccountTokenCreator on per-action-class SAs."
}

# ---------------------------------------------------------------------------
# Per-action-class execution SAs.
# The Broker impersonates each for short-lived write operations.
# No exported keys — impersonation only via generateAccessToken.
# ---------------------------------------------------------------------------

resource "google_service_account" "action_cloudrun_scale" {
  project      = var.project_id
  account_id   = "sa-action-cloudrun-scale"
  display_name = "AOP action SA — cloud_run.scale_within_range"
  description  = "Least-privilege SA for Cloud Run scaling actions."
}

resource "google_service_account" "action_cloudrun_rollback" {
  project      = var.project_id
  account_id   = "sa-action-cloudrun-rollback"
  display_name = "AOP action SA — cloud_run.rollback_to_previous"
  description  = "Least-privilege SA for Cloud Run rollback actions."
}

resource "google_service_account" "action_iam_disable_key" {
  project      = var.project_id
  account_id   = "sa-action-iam-disable-key"
  display_name = "AOP action SA — iam.disable_service_account_key"
  description  = "Least-privilege SA for disabling SA keys."
}

resource "google_service_account" "action_secret_disable" {
  project      = var.project_id
  account_id   = "sa-action-secret-disable"
  display_name = "AOP action SA — secret_manager.disable_version"
  description  = "Least-privilege SA for disabling Secret Manager versions."
}

resource "google_service_account" "action_scc_mute" {
  project      = var.project_id
  account_id   = "sa-action-scc-mute"
  display_name = "AOP action SA — scc.mute_finding"
  description  = "Least-privilege SA for muting SCC findings."
}

resource "google_service_account" "action_workflows_run" {
  project      = var.project_id
  account_id   = "sa-action-workflows-run"
  display_name = "AOP action SA — workflows.run"
  description  = "Least-privilege SA for invoking Cloud Workflows."
}

resource "google_service_account" "action_terraform_plan" {
  project      = var.project_id
  account_id   = "sa-action-terraform-plan"
  display_name = "AOP action SA — terraform.plan"
  description  = "Read-only SA for generating Terraform plans (no apply)."
}

# ---------------------------------------------------------------------------
# Role grants on per-action-class SAs (least-privilege).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Custom roles — narrower than the predefined alternatives.
#
# Predefined roles like roles/secretmanager.admin or
# roles/iam.serviceAccountKeyAdmin bundle write + delete + setIamPolicy
# permissions far broader than the action class actually needs. The custom
# roles below grant ONLY the minimum permission set required by the matching
# executor in services/action-broker/executors/.
# ---------------------------------------------------------------------------

# disable-only on SA keys. Strictly tighter than
# roles/iam.serviceAccountKeyAdmin which also grants keys.create and
# keys.delete (delete = harder than disable; create = grants key minting).
resource "google_project_iam_custom_role" "iam_sa_key_disable" {
  project     = var.project_id
  role_id     = "aopIamServiceAccountKeyDisableOnly"
  title       = "AOP — IAM SA key disable only"
  description = "Disable + read on service account keys; no create, no delete. Scoped to the iam.disable_service_account_key action class executor."
  permissions = [
    "iam.serviceAccountKeys.disable",
    "iam.serviceAccountKeys.get",
    "iam.serviceAccountKeys.list",
  ]
  stage = "GA"
}

# disable-only on Secret Manager versions. Tighter than
# roles/secretmanager.admin which grants create/delete/setIamPolicy.
resource "google_project_iam_custom_role" "secret_version_disable" {
  project     = var.project_id
  role_id     = "aopSecretVersionDisableOnly"
  title       = "AOP — Secret version disable only"
  description = "Disable + read on Secret Manager secret versions. Scoped to the secret_manager.disable_version action class executor."
  permissions = [
    "secretmanager.secrets.get",
    "secretmanager.secrets.list",
    "secretmanager.versions.get",
    "secretmanager.versions.list",
    "secretmanager.versions.disable",
  ]
  stage = "GA"
}

# setMute-only on SCC findings. Tighter than
# roles/securitycenter.findingsEditor which also grants findings.update +
# findings.setState (state change can resolve / dismiss findings outright).
resource "google_project_iam_custom_role" "scc_mute_finding" {
  project     = var.project_id
  role_id     = "aopSccFindingMuteOnly"
  title       = "AOP — SCC finding mute only"
  description = "setMute + read on Security Command Center findings. Scoped to the scc.mute_finding action class executor."
  permissions = [
    "securitycenter.findings.get",
    "securitycenter.findings.list",
    "securitycenter.findings.setMute",
  ]
  stage = "GA"
}

# Cloud Run scale: roles/run.developer is the narrowest predefined role that
# grants services.update. Tighter scoping (specific service name) is enforced
# by the executor + policy bounds rather than by IAM, because IAM conditions
# on services/v2 resource paths require name patterns the action API cannot
# always provide ahead of time. See policy/action_classes.yaml bounds.
resource "google_project_iam_member" "cloudrun_scale_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.action_cloudrun_scale.email}"
}

resource "google_project_iam_member" "cloudrun_rollback_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.action_cloudrun_rollback.email}"
}

resource "google_project_iam_member" "iam_disable_key" {
  project = var.project_id
  role    = google_project_iam_custom_role.iam_sa_key_disable.id
  member  = "serviceAccount:${google_service_account.action_iam_disable_key.email}"
}

resource "google_project_iam_member" "secret_disable" {
  project = var.project_id
  role    = google_project_iam_custom_role.secret_version_disable.id
  member  = "serviceAccount:${google_service_account.action_secret_disable.email}"
}

resource "google_project_iam_member" "scc_mute_finding" {
  project = var.project_id
  role    = google_project_iam_custom_role.scc_mute_finding.id
  member  = "serviceAccount:${google_service_account.action_scc_mute.email}"
}

# workflows.invoker: predefined role is project-wide. When
# `var.workflows_invoker_resource_pattern` is set, the binding is conditioned
# on the workflow resource name matching the pattern (regex). Empty default
# preserves the broader project-wide grant so existing deployments are not
# broken — set the variable in tfvars to scope.
resource "google_project_iam_member" "workflows_run_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.action_workflows_run.email}"

  dynamic "condition" {
    for_each = var.workflows_invoker_resource_pattern != "" ? [1] : []
    content {
      title       = "workflows-only-${replace(var.workflows_invoker_resource_pattern, "/[^a-zA-Z0-9]/", "")}"
      description = "Limit workflows.invoker to workflow resources matching the AOP-managed pattern."
      expression  = "resource.name.startsWith(\"projects/${var.project_id}/locations/${var.region}/workflows/${var.workflows_invoker_resource_pattern}\")"
    }
  }
}

# terraform.plan: roles/viewer is the standard read-only blanket. Read-only
# is safe by definition (no mutations possible), but it does grant read on
# secrets metadata (NOT the payload) and on Secret Manager IAM. Document as
# acceptable; revisit if a narrower predefined role appears upstream.
resource "google_project_iam_member" "terraform_plan_viewer" {
  # checkov:skip=CKV_GCP_117: terraform plan needs broad read across all resource types; roles/viewer is read-only (no mutations), impersonation- and broker-gated, and no narrower predefined role covers arbitrary plan reads.
  project = var.project_id
  role    = "roles/viewer"
  member  = "serviceAccount:${google_service_account.action_terraform_plan.email}"
}

# ---------------------------------------------------------------------------
# Broker impersonation rights — iam.serviceAccountTokenCreator on each action SA
# This is the ONLY write-like grant the broker SA holds.
# ---------------------------------------------------------------------------

resource "google_service_account_iam_member" "broker_impersonate_cloudrun_scale" {
  service_account_id = google_service_account.action_cloudrun_scale.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_service_account_iam_member" "broker_impersonate_cloudrun_rollback" {
  service_account_id = google_service_account.action_cloudrun_rollback.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_service_account_iam_member" "broker_impersonate_iam_disable_key" {
  service_account_id = google_service_account.action_iam_disable_key.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_service_account_iam_member" "broker_impersonate_secret_disable" {
  service_account_id = google_service_account.action_secret_disable.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_service_account_iam_member" "broker_impersonate_scc_mute" {
  service_account_id = google_service_account.action_scc_mute.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_service_account_iam_member" "broker_impersonate_workflows_run" {
  service_account_id = google_service_account.action_workflows_run.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_service_account_iam_member" "broker_impersonate_terraform_plan" {
  service_account_id = google_service_account.action_terraform_plan.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.action_broker.email}"
}

# ---------------------------------------------------------------------------
# Pub/Sub grants for broker
# ---------------------------------------------------------------------------

resource "google_pubsub_topic_iam_member" "broker_actions_requested_publisher" {
  project = var.project_id
  topic   = var.ops_actions_requested_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_pubsub_topic_iam_member" "broker_actions_executed_publisher" {
  project = var.project_id
  topic   = var.ops_actions_executed_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.action_broker.email}"
}

resource "google_pubsub_topic_iam_member" "broker_audit_publisher" {
  project = var.project_id
  topic   = var.ops_audit_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.action_broker.email}"
}

# ---------------------------------------------------------------------------
# Secrets — broker reads Slack signing secret (for webhook validation) + policy key
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "broker_policy_key" {
  project   = var.project_id
  secret_id = "broker-policy-key"

  replication {
    auto {}
  }

  labels = local.common_labels
}

resource "google_secret_manager_secret_iam_member" "broker_policy_key_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.broker_policy_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.action_broker.email}"
}

# ---------------------------------------------------------------------------
# Pub/Sub push subscription on ops.actions.approved → broker
# ---------------------------------------------------------------------------

resource "google_pubsub_subscription" "ops_actions_approved_push" {
  project = var.project_id
  name    = "ops.actions.approved.broker-push"
  topic   = var.ops_actions_approved_topic_id

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.action_broker.uri}/pubsub/approved"
    oidc_token {
      service_account_email = google_service_account.action_broker.email
    }
  }

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s" # 7 days

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Cloud Run v2 service — action-broker
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "action_broker" {
  project  = var.project_id
  name     = "action-broker"
  location = var.region

  template {
    service_account = google_service_account.action_broker.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.container_image

      env {
        name  = "ENV"
        value = var.env
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "REGION"
        value = var.region
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      liveness_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 30
        failure_threshold     = 3
      }
    }
  }

  labels = local.common_labels

  # Require authentication — no unauthenticated invocations
  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}

# ---------------------------------------------------------------------------
# Broker invoker grants — explicit allow-list. The Cloud Run service runs
# with ingress=INTERNAL_LOAD_BALANCER (network-layer fence) AND requires
# authenticated invocation (IAM-layer fence). Only the principals listed
# below can call the broker.
#
# Self-grant: the Pub/Sub push subscription on ops.actions.approved mints an
# OIDC token using sa-action-broker; that token must satisfy run.invoker on
# this same service. This is the minimum binding required for the push path.
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "broker_self_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.action_broker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.action_broker.email}"
}

# Agent invoker grants — wired from the env root after agent_runtime applies.
# Empty default = broker only callable by itself (the self-invoker above),
# which is the safe state until agent SAs are known. The env-root composes
# the cross-module dependency: see environments/<env>/main.tf.
resource "google_cloud_run_v2_service_iam_member" "broker_invoker_agents" {
  for_each = toset(var.agent_sa_emails)

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.action_broker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value}"
}
