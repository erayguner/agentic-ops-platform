locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "slack-notifier"
      managed_by = "terraform"
    },
    var.labels,
  )
}

# ---------------------------------------------------------------------------
# Service account — sa-slack-notifier
# ---------------------------------------------------------------------------

resource "google_service_account" "slack_notifier" {
  project      = var.project_id
  account_id   = "sa-slack-notifier"
  display_name = "AOP Slack Notifier SA"
  description  = "Identity for the slack-notifier Cloud Run service."
}

# ---------------------------------------------------------------------------
# Secrets — Slack OAuth token and signing secret
# Actual values are set out-of-band; never committed to version control.
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "slack_oauth_token" {
  project   = var.project_id
  secret_id = "slack-oauth-token"

  replication {
    auto {}
  }

  labels = local.common_labels
}

resource "google_secret_manager_secret" "slack_signing_secret" {
  project   = var.project_id
  secret_id = "slack-signing-secret"

  replication {
    auto {}
  }

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# IAM — notifier SA reads Slack secrets
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret_iam_member" "notifier_oauth_token_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.slack_oauth_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.slack_notifier.email}"
}

resource "google_secret_manager_secret_iam_member" "notifier_signing_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.slack_signing_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.slack_notifier.email}"
}

# ---------------------------------------------------------------------------
# IAM — notifier publishes to ops.actions.approved (Slack interactivity handler)
# DESIGN-REVIEW §5.3: slack-notifier needs pubsub.publisher on ops.actions.approved
# ---------------------------------------------------------------------------

resource "google_pubsub_topic_iam_member" "notifier_actions_approved_publisher" {
  project = var.project_id
  topic   = var.ops_actions_approved_topic_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.slack_notifier.email}"
}

# ---------------------------------------------------------------------------
# Pub/Sub push subscription — ops.notifications → notifier /pubsub/push
# ---------------------------------------------------------------------------

resource "google_pubsub_subscription" "ops_notifications_push" {
  project = var.project_id
  name    = "ops.notifications.notifier-push"
  topic   = var.ops_notifications_topic_id

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.slack_notifier.uri}/pubsub/push"
    oidc_token {
      service_account_email = google_service_account.slack_notifier.email
    }
  }

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Cloud Run v2 service — slack-notifier
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "slack_notifier" {
  project  = var.project_id
  name     = "slack-notifier"
  location = var.region

  template {
    service_account = google_service_account.slack_notifier.email

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
        name  = "SLACK_CHANNEL_INCIDENTS"
        value = var.slack_channel_incidents
      }
      env {
        name  = "SLACK_CHANNEL_SECURITY"
        value = var.slack_channel_security
      }
      env {
        name  = "SLACK_CHANNEL_FINOPS"
        value = var.slack_channel_finops
      }
      env {
        name  = "SLACK_CHANNEL_PLATFORM"
        value = var.slack_channel_platform
      }
      env {
        name = "SLACK_OAUTH_TOKEN_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.slack_oauth_token.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SLACK_SIGNING_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.slack_signing_secret.secret_id
            version = "latest"
          }
        }
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

  # Require authentication for all paths except /slack/events (handled by signing secret)
  ingress = "INGRESS_TRAFFIC_ALL"
}

# Allow Pub/Sub service agent to invoke the notifier (for OIDC push)
resource "google_cloud_run_v2_service_iam_member" "notifier_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.slack_notifier.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.slack_notifier.email}"
}
