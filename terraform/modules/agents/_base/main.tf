locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "agent"
      agent      = var.agent_slug
      managed_by = "terraform"
    },
    var.labels,
  )

  deletion_policy = var.deletion_policy_prevent ? "PREVENT" : "DELETE"

  package_uri = (
    var.package_pickle_gcs_uri != ""
    ? var.package_pickle_gcs_uri
    : "gs://REPLACE_BUCKET/${var.agent_slug}/agent.pkl"
  )

  sa_account_id = "sa-${var.agent_slug}"
  sa_description = (
    var.service_account_description != ""
    ? var.service_account_description
    : "Identity for the AOP ${var.agent_slug} reasoning engine. Read-only; write actions go through the Action Broker."
  )

  # Stable keys → topic resource IDs. Keys are literal strings ("audit",
  # "findings", "notifications", …) so Terraform can plan the for_each map
  # even when individual topic IDs are unknown until apply.
  publish_topics = merge(
    { audit = var.ops_audit_topic_id },
    var.extra_pubsub_publish_topics,
  )
  subscribe_topics = var.extra_pubsub_subscribe_topics

  predefined_roles = toset(var.project_iam_roles)
  custom_roles     = toset(var.custom_project_iam_role_ids)
}

# ---------------------------------------------------------------------------
# Service account — one per agent. No exported keys; only impersonation paths.
# ---------------------------------------------------------------------------

resource "google_service_account" "this" {
  project      = var.project_id
  account_id   = local.sa_account_id
  display_name = "AOP ${var.agent_display_name} SA"
  description  = local.sa_description
}

# ---------------------------------------------------------------------------
# Project IAM — predefined roles (allow-listed by the variable validator).
# ---------------------------------------------------------------------------

resource "google_project_iam_member" "predefined" {
  for_each = local.predefined_roles

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.this.email}"
}

resource "google_project_iam_member" "custom" {
  for_each = local.custom_roles

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.this.email}"
}

# Read-only Google Cloud MCP access. roles/mcp.toolUser only permits invoking the
# MCP tool surface; the data each agent can read is bounded by the viewer roles
# passed via var.project_iam_roles (least privilege). Writes go via the Action
# Broker. See docs/deployment/MCP-SERVERS.md.
resource "google_project_iam_member" "mcp_tool_user" {
  project = var.project_id
  role    = "roles/mcp.toolUser"
  member  = "serviceAccount:${google_service_account.this.email}"
}

# ---------------------------------------------------------------------------
# Pub/Sub publisher bindings — audit topic is required; others are optional.
# ---------------------------------------------------------------------------

resource "google_pubsub_topic_iam_member" "publisher" {
  for_each = local.publish_topics

  project = var.project_id
  topic   = each.value
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.this.email}"
}

resource "google_pubsub_topic_iam_member" "subscriber" {
  for_each = local.subscribe_topics

  project = var.project_id
  topic   = each.value
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.this.email}"
}

# ---------------------------------------------------------------------------
# Reasoning Engine — GA surface, no Memory Bank.
# ---------------------------------------------------------------------------

resource "google_vertex_ai_reasoning_engine" "this" {
  project      = var.project_id
  region       = var.region
  display_name = "AOP ${var.agent_display_name} (${var.env})"
  description  = var.agent_description

  spec {
    agent_framework = var.agent_framework
    package_spec {
      python_version        = var.package_python_version
      pickle_object_gcs_uri = local.package_uri
      requirements_gcs_uri  = var.package_requirements_gcs_uri != "" ? var.package_requirements_gcs_uri : null
    }
  }

  deletion_policy = local.deletion_policy
}

# ---------------------------------------------------------------------------
# Memory Bank variant (optional, beta provider). Separate resource because
# context_spec is only available on google-beta at provider 7.33.
# Remove the `provider = google-beta` line once context_spec graduates.
# ---------------------------------------------------------------------------

resource "google_vertex_ai_reasoning_engine" "memory_bank" {
  count = var.enable_memory_bank ? 1 : 0

  provider     = google-beta # BETA: context_spec.memory_bank_config is GA-pending.
  project      = var.project_id
  region       = var.region
  display_name = "AOP ${var.agent_display_name} — Memory Bank (${var.env})"
  description  = "${var.agent_description} (Memory Bank-enabled variant)"

  spec {
    agent_framework = var.agent_framework
    package_spec {
      python_version        = var.package_python_version
      pickle_object_gcs_uri = local.package_uri
      requirements_gcs_uri  = var.package_requirements_gcs_uri != "" ? var.package_requirements_gcs_uri : null
    }
  }

  context_spec {
    memory_bank_config {}
  }

  deletion_policy = local.deletion_policy
}

# ---------------------------------------------------------------------------
# Optional Cloud Scheduler trigger — periodic HTTP POST against the agent's
# entry-point. The agent SA itself is used as the OIDC identity; the target
# endpoint MUST be configured to accept tokens from that SA.
# ---------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "trigger" {
  count = var.schedule != null ? 1 : 0

  project          = var.project_id
  region           = var.region
  name             = "aop-${var.agent_slug}-trigger"
  description      = "Scheduled trigger for the AOP ${var.agent_display_name} agent."
  schedule         = var.schedule.cron
  time_zone        = coalesce(try(var.schedule.timezone, null), "Etc/UTC")
  attempt_deadline = "600s"

  retry_config {
    retry_count          = 1
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "60s"
    max_doublings        = 5
  }

  http_target {
    uri         = var.schedule.target_uri
    http_method = "POST"
    body        = base64encode(coalesce(try(var.schedule.body, null), "{}"))

    headers = merge(
      { "Content-Type" = "application/json" },
      coalesce(try(var.schedule.headers, null), {}),
    )

    oidc_token {
      service_account_email = google_service_account.this.email
      audience              = var.schedule.target_uri
    }
  }
}

# ---------------------------------------------------------------------------
# Terraform-native health checks — surface configuration drift at plan time.
# These do not produce resources; they fail the plan with a diagnostic if
# the assertion does not hold.
# ---------------------------------------------------------------------------

check "agent_sa_email_assigned" {
  assert {
    condition     = google_service_account.this.email != ""
    error_message = "Agent service account email is empty — SA creation likely failed for ${var.agent_slug}."
  }
}

check "reasoning_engine_package_uri_real" {
  assert {
    condition     = !startswith(local.package_uri, "gs://REPLACE_BUCKET/")
    error_message = "Reasoning engine for ${var.agent_slug} is still using the placeholder pickle URI; set package_pickle_gcs_uri before applying to a non-skeleton environment."
  }
}

check "schedule_endpoint_is_https" {
  assert {
    condition     = var.schedule == null || startswith(var.schedule.target_uri, "https://")
    error_message = "Cloud Scheduler target_uri for ${var.agent_slug} must be HTTPS."
  }
}
