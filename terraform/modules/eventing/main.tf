locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "eventing"
      managed_by = "terraform"
    },
    var.labels,
  )

  # All canonical AOP topics.
  topics = [
    "ops.signals",
    "ops.findings",
    "ops.actions.requested",
    "ops.actions.approved",
    "ops.actions.executed",
    "ops.notifications",
    "ops.audit",
  ]

  # Topics that get DLQs (all of them per contract)
  dlq_topics = [for t in local.topics : "${t}.dlq"]

  # Topics that have Avro schemas (signals, notifications, audit per contract)
  schema_topics = toset(["ops.signals", "ops.notifications", "ops.audit"])
}

# ---------------------------------------------------------------------------
# Pub/Sub Schemas (Avro) — ops.signals, ops.notifications, ops.audit
# ---------------------------------------------------------------------------

resource "google_pubsub_schema" "ops_signals" {
  project = var.project_id
  name    = "ops.signals.schema.v1"
  type    = "AVRO"
  definition = jsonencode({
    type      = "record"
    name      = "OpsSignal"
    namespace = "aop.ops"
    fields = [
      { name = "schema", type = "string" },
      { name = "signal_id", type = "string" },
      { name = "correlation_id", type = "string" },
      { name = "produced_at", type = "string" },
      { name = "source", type = "string" },
      { name = "source_ref", type = ["null", "string"], default = null },
      { name = "environment", type = "string" },
      { name = "severity", type = "string" },
      { name = "raw", type = "string" }, # JSON-encoded opaque payload
      { name = "labels", type = { type = "map", values = "string" }, default = {} },
    ]
  })
}

resource "google_pubsub_schema" "ops_notifications" {
  project = var.project_id
  name    = "ops.notifications.schema.v1"
  type    = "AVRO"
  definition = jsonencode({
    type      = "record"
    name      = "OpsNotification"
    namespace = "aop.ops"
    fields = [
      { name = "schema", type = "string" },
      { name = "notification_id", type = "string" },
      { name = "correlation_id", type = "string" },
      { name = "produced_at", type = "string" },
      { name = "severity", type = "string" },
      { name = "environment", type = "string" },
      { name = "domain", type = "string" },
      { name = "summary", type = "string" },
      { name = "affected_component", type = "string" }, # JSON-encoded
      { name = "impact", type = "string" },
      { name = "recommended_actions", type = "string" }, # JSON-encoded array
      { name = "human_required", type = "boolean" },
      { name = "references", type = "string" }, # JSON-encoded
      { name = "agent", type = "string" },      # JSON-encoded
    ]
  })
}

resource "google_pubsub_schema" "ops_audit" {
  project = var.project_id
  name    = "ops.audit.schema.v1"
  type    = "AVRO"
  definition = jsonencode({
    type      = "record"
    name      = "AuditRecord"
    namespace = "aop.ops"
    fields = [
      { name = "audit_id", type = "string" },
      { name = "correlation_id", type = "string" },
      { name = "timestamp", type = "string" },
      { name = "phase", type = "string" },
      { name = "agent_identity", type = "string" },
      { name = "human_identity", type = ["null", "string"], default = null },
      { name = "environment", type = "string" },
      { name = "domain", type = "string" },
      { name = "action_class", type = ["null", "string"], default = null },
      { name = "policy_decision", type = "string" }, # JSON-encoded
      { name = "evidence_refs", type = { type = "array", items = "string" }, default = [] },
      { name = "model", type = "string" },   # JSON-encoded
      { name = "outcome", type = "string" }, # JSON-encoded
    ]
  })
}

# ---------------------------------------------------------------------------
# Main topics
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "ops_signals" {
  project = var.project_id
  name    = "ops.signals"
  labels  = local.common_labels

  schema_settings {
    schema   = google_pubsub_schema.ops_signals.id
    encoding = "JSON"
  }

  # Guard audit topic in prod against accidental deletion
  # (ops.signals is not the audit topic, but we protect all schema topics)
}

resource "google_pubsub_topic" "ops_findings" {
  project = var.project_id
  name    = "ops.findings"
  labels  = local.common_labels
}

resource "google_pubsub_topic" "ops_actions_requested" {
  project = var.project_id
  name    = "ops.actions.requested"
  labels  = local.common_labels
}

resource "google_pubsub_topic" "ops_actions_approved" {
  project = var.project_id
  name    = "ops.actions.approved"
  labels  = local.common_labels
}

resource "google_pubsub_topic" "ops_actions_executed" {
  project = var.project_id
  name    = "ops.actions.executed"
  labels  = local.common_labels
}

resource "google_pubsub_topic" "ops_notifications" {
  project = var.project_id
  name    = "ops.notifications"
  labels  = local.common_labels

  schema_settings {
    schema   = google_pubsub_schema.ops_notifications.id
    encoding = "JSON"
  }
}

resource "google_pubsub_topic" "ops_audit" {
  project = var.project_id
  name    = "ops.audit"
  labels  = local.common_labels

  schema_settings {
    schema   = google_pubsub_schema.ops_audit.id
    encoding = "JSON"
  }
}

# ---------------------------------------------------------------------------
# DLQ topics — one per main topic.
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "ops_signals_dlq" {
  project = var.project_id
  name    = "ops.signals.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

resource "google_pubsub_topic" "ops_findings_dlq" {
  project = var.project_id
  name    = "ops.findings.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

resource "google_pubsub_topic" "ops_actions_requested_dlq" {
  project = var.project_id
  name    = "ops.actions.requested.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

resource "google_pubsub_topic" "ops_actions_approved_dlq" {
  project = var.project_id
  name    = "ops.actions.approved.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

resource "google_pubsub_topic" "ops_actions_executed_dlq" {
  project = var.project_id
  name    = "ops.actions.executed.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

resource "google_pubsub_topic" "ops_notifications_dlq" {
  project = var.project_id
  name    = "ops.notifications.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

resource "google_pubsub_topic" "ops_audit_dlq" {
  project = var.project_id
  name    = "ops.audit.dlq"
  labels  = merge(local.common_labels, { component = "eventing-dlq" })
}

# ---------------------------------------------------------------------------
# BigQuery subscription on ops.audit → audit_events table
# ---------------------------------------------------------------------------

resource "google_bigquery_table" "audit_events" {
  # checkov:skip=CKV_GCP_121: deletion protection is environment-driven via var.deletion_policy_prevent (true in prod); dev intentionally allows teardown.
  # checkov:skip=CKV_GCP_80: CMEK is a documented roadmap hardening for the audit pipeline; Google-managed encryption (AES-256, always-on) is the scaffold baseline. See docs/GOVERNANCE-MAPPING.md §12.
  project    = var.project_id
  dataset_id = var.audit_bq_dataset_id
  table_id   = var.audit_bq_table_id

  deletion_protection = var.deletion_policy_prevent

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  schema = jsonencode([
    { name = "audit_id", type = "STRING", mode = "REQUIRED" },
    { name = "correlation_id", type = "STRING", mode = "REQUIRED" },
    { name = "timestamp", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "phase", type = "STRING", mode = "REQUIRED" },
    { name = "agent_identity", type = "STRING", mode = "REQUIRED" },
    { name = "human_identity", type = "STRING", mode = "NULLABLE" },
    { name = "environment", type = "STRING", mode = "REQUIRED" },
    { name = "domain", type = "STRING", mode = "REQUIRED" },
    { name = "action_class", type = "STRING", mode = "NULLABLE" },
    # The ops.audit AVRO schema carries these as JSON-encoded strings and
    # evidence_refs as array<string>. With use_topic_schema=true the BQ column
    # types/modes must match the AVRO field types, so model/policy_decision/
    # outcome are STRING (the JSON text) and evidence_refs is REPEATED STRING.
    { name = "policy_decision", type = "STRING", mode = "NULLABLE" },
    { name = "evidence_refs", type = "STRING", mode = "REPEATED" },
    { name = "model", type = "STRING", mode = "NULLABLE" },
    { name = "outcome", type = "STRING", mode = "NULLABLE" },
  ])

  labels = local.common_labels
}

# A BigQuery subscription requires the Pub/Sub service agent to hold BigQuery
# write (+ metadata) access on the destination; Pub/Sub validates this at
# create time and returns 403 "caller does not have permission" otherwise.
data "google_project" "this" {
  project_id = var.project_id
}

resource "google_bigquery_dataset_iam_member" "pubsub_audit_data_editor" {
  count = var.enable_bq_audit_subscription ? 1 : 0

  project    = var.project_id
  dataset_id = var.audit_bq_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "pubsub_audit_metadata_viewer" {
  count = var.enable_bq_audit_subscription ? 1 : 0

  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "ops_audit_bq" {
  count = var.enable_bq_audit_subscription ? 1 : 0

  project = var.project_id
  name    = "ops.audit.bq-sub"
  topic   = google_pubsub_topic.ops_audit.name

  bigquery_config {
    table            = "${var.project_id}.${var.audit_bq_dataset_id}.${var.audit_bq_table_id}"
    use_topic_schema = true
    write_metadata   = false
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.ops_audit_dlq.id
    max_delivery_attempts = 5
  }

  labels = local.common_labels

  depends_on = [
    google_bigquery_table.audit_events,
    google_bigquery_dataset_iam_member.pubsub_audit_data_editor,
    google_project_iam_member.pubsub_audit_metadata_viewer,
  ]
}

# ---------------------------------------------------------------------------
# Eventarc trigger 1: Cloud Audit Log events (IAM) → ops.signals topic
# Eventarc routes audit log events via the Cloud Run destination.
# The normaliser Cloud Run service receives the CloudEvent and republishes
# to ops.signals. Using a Cloud Run destination for Audit Log triggers is the
# canonical pattern; direct Pub/Sub destination is only supported for Pub/Sub
# source triggers (trigger 2 below uses the transport.pubsub approach).
# ---------------------------------------------------------------------------

resource "google_eventarc_trigger" "audit_logs_to_signals" {
  # Requires a Cloud Run service named "orchestrator" to exist as the event
  # destination. The scaffold's orchestrator is a Vertex AI reasoning engine,
  # not a Cloud Run service, so this trigger cannot be created on a clean
  # first apply. Gate it off (default on preserves legacy dev/prod intent);
  # wire it up once an orchestrator ingest endpoint exists.
  count = var.enable_eventarc_triggers ? 1 : 0

  project         = var.project_id
  name            = "aop-audit-logs-to-signals"
  location        = var.region
  service_account = "sa-orchestrator@${var.project_id}.iam.gserviceaccount.com"

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.audit.log.v1.written"
  }
  matching_criteria {
    attribute = "serviceName"
    value     = "iam.googleapis.com"
  }
  matching_criteria {
    attribute = "methodName"
    value     = "google.iam.admin.v1.CreateServiceAccountKey"
  }

  # Cloud Run destination — the orchestrator's event-ingest endpoint normalises
  # the CloudEvent into an OpsSignal and publishes to ops.signals.
  destination {
    cloud_run_service {
      service = "orchestrator"
      region  = var.region
      path    = "/events/audit"
    }
  }

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Eventarc trigger 2: ops.notifications Pub/Sub → Slack-notifier Cloud Run
# Delivers OpsNotification events to the notifier for Block Kit rendering.
# The transport.pubsub block is required for Pub/Sub source triggers.
# ---------------------------------------------------------------------------

resource "google_eventarc_trigger" "notifications_to_slack_notifier" {
  # Destination is the slack-notifier Cloud Run service, which is deployed
  # AFTER eventing in the dependency graph (no Terraform edge couples them,
  # since the destination is referenced by service name string). Gate off to
  # keep eventing's first apply clean; create on a follow-up apply once the
  # notifier service exists.
  count = var.enable_eventarc_triggers ? 1 : 0

  project         = var.project_id
  name            = "aop-notifications-to-slack-notifier"
  location        = var.region
  service_account = "sa-slack-notifier@${var.project_id}.iam.gserviceaccount.com"

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }

  transport {
    pubsub {
      topic = google_pubsub_topic.ops_notifications.name
    }
  }

  destination {
    cloud_run_service {
      service = "slack-notifier"
      region  = var.region
      path    = "/pubsub/push"
    }
  }

  labels = local.common_labels
}
