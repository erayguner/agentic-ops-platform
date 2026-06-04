locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "governance"
      managed_by = "terraform"
    },
    var.labels,
  )

  has_org    = var.org_id != ""
  has_folder = var.folder_id != ""
}

# ---------------------------------------------------------------------------
# BigQuery dataset for audit log sink destination
# ---------------------------------------------------------------------------

resource "google_bigquery_dataset" "audit_logs" {
  project     = var.project_id
  dataset_id  = var.audit_bq_dataset_id
  location    = "EU"
  description = "Immutable AOP audit log export from Cloud Logging"

  # Prevent `terraform destroy`/replacement from dropping the audit store
  # (compliance evidence) when enabled. Mirrors agent-runtime's deletion policy
  # and the ops.audit topic protection in the prod root.
  deletion_policy = var.deletion_policy_prevent ? "PREVENT" : "DELETE"

  default_table_expiration_ms = null # retention managed by table-level policies

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Audit log sink: all logs → BigQuery
# ---------------------------------------------------------------------------

resource "google_logging_project_sink" "audit_bq" {
  project                = var.project_id
  name                   = var.log_sink_name
  destination            = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${google_bigquery_dataset.audit_logs.dataset_id}"
  filter                 = "" # _AllLogs
  unique_writer_identity = true

  bigquery_options {
    use_partitioned_tables = true
  }

  description = "AOP audit log sink: all logs to BigQuery for compliance retention."
}

# Grant the sink's writer SA access to write to the BQ dataset
resource "google_bigquery_dataset_iam_member" "audit_sink_writer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.audit_logs.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.audit_bq.writer_identity
}

# ---------------------------------------------------------------------------
# Model Armor floor setting (project scope)
# parent = projects/<project_id> (required; no separate project/location args)
# enable_floor_setting_enforcement = true enables INSPECT_AND_BLOCK mode.
# google_mcp_server_floor_setting block enables screening of MCP server traffic.
# ---------------------------------------------------------------------------

resource "google_model_armor_floorsetting" "project" {
  parent   = "projects/${var.project_id}"
  location = var.model_armor_location

  # INSPECT_AND_BLOCK: requests failing the floor policy are blocked, not just logged.
  enable_floor_setting_enforcement = true

  # Enable Model Armor screening for all integrated Google MCP Servers.
  google_mcp_server_floor_setting {
    inspect_and_block = true
  }

  filter_config {
    rai_settings {
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "SEXUALLY_EXPLICIT"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "HARASSMENT"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "DANGEROUS_CONTENT"
        confidence_level = "LOW_AND_ABOVE"
      }
    }
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "LOW_AND_ABOVE"
    }
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }
    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Model Armor template — prompt-injection + sensitive-data starter
# ---------------------------------------------------------------------------

resource "google_model_armor_template" "aop_default" {
  project     = var.project_id
  location    = var.model_armor_location
  template_id = "aop-default-v1"

  filter_config {
    rai_settings {
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "LOW_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "DANGEROUS_CONTENT"
        confidence_level = "LOW_AND_ABOVE"
      }
    }
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "LOW_AND_ABOVE"
    }
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }
    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Security Command Center — project-scoped notification config (non-v2)
# google_scc_v2_project_source does not exist in the GA provider at 7.33.
# Use google_scc_project_notification_config (project-scoped, GA) instead.
# For org-scoped SCC source, use google_scc_v2_organization_source when
# an org is available.
# ---------------------------------------------------------------------------

resource "google_scc_project_notification_config" "aop" {
  project      = var.project_id
  config_id    = "aop-scc-notify"
  description  = "AOP: route SCC findings to ops.signals Pub/Sub topic"
  pubsub_topic = var.scc_notification_pubsub_topic

  streaming_config {
    filter = "severity = \"CRITICAL\" OR severity = \"HIGH\""
  }
}

# ---------------------------------------------------------------------------
# SCC v2 BigQuery export (project scope) — routes all findings to audit BQ
# ---------------------------------------------------------------------------

resource "google_scc_project_scc_big_query_export" "aop" {
  project             = var.project_id
  big_query_export_id = "aop-scc-bq-export"
  description         = "Export all SCC findings to BigQuery for AOP analytics and compliance."
  dataset             = "projects/${var.project_id}/datasets/${google_bigquery_dataset.audit_logs.dataset_id}"
  filter              = "" # all findings
}

# ---------------------------------------------------------------------------
# Example: org-scoped SCC source (uncomment when org_id is set)
# ---------------------------------------------------------------------------
#
# resource "google_scc_v2_organization_source" "aop" {
#   count        = local.has_org ? 1 : 0
#   organization = var.org_id
#   display_name = "AOP Platform Security"
#   description  = "Security findings emitted by the AOP DevSecOps agent and platform controls."
# }

# ---------------------------------------------------------------------------
# Org Policy examples (project scope; org/folder variants commented out)
# ---------------------------------------------------------------------------

# Disable SA key creation — prevents re-introduction of long-lived credentials.
resource "google_org_policy_policy" "disable_sa_key_creation" {
  name   = "projects/${var.project_id}/policies/iam.disableServiceAccountKeyCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Restrict resource locations to EU — data-residency baseline.
resource "google_org_policy_policy" "resource_locations" {
  name   = "projects/${var.project_id}/policies/gcp.resourceLocations"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      values {
        allowed_values = ["in:eu-locations"]
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Example: folder-scoped variants (uncomment and set folder_id to activate)
# ---------------------------------------------------------------------------
#
# resource "google_org_policy_policy" "folder_disable_sa_key_creation" {
#   count  = local.has_folder ? 1 : 0
#   name   = "folders/${var.folder_id}/policies/iam.disableServiceAccountKeyCreation"
#   parent = "folders/${var.folder_id}"
#   spec {
#     rules { enforce = "TRUE" }
#   }
# }
#
# resource "google_org_policy_policy" "org_resource_locations" {
#   count  = local.has_org ? 1 : 0
#   name   = "organizations/${var.org_id}/policies/gcp.resourceLocations"
#   parent = "organizations/${var.org_id}"
#   spec {
#     rules {
#       values { allowed_values = ["in:eu-locations"] }
#     }
#   }
# }

# ---------------------------------------------------------------------------
# Custom IAM role — Auditor (read-only access to audit datasets + SCC)
# ---------------------------------------------------------------------------

resource "google_project_iam_custom_role" "auditor" {
  project     = var.project_id
  role_id     = "aopAuditor"
  title       = "AOP Auditor"
  description = "Read-only access to AOP audit datasets, SCC findings, and Cloud Logging for compliance review."

  permissions = [
    "bigquery.datasets.get",
    "bigquery.tables.get",
    "bigquery.tables.list",
    "bigquery.tables.getData",
    "logging.logEntries.list",
    "logging.logs.list",
    "logging.sinks.get",
    "logging.sinks.list",
    "securitycenter.findings.list",
    "securitycenter.findings.group",
    "securitycenter.sources.list",
    "securitycenter.sources.get",
    "monitoring.alertPolicies.list",
    "monitoring.alertPolicies.get",
    "monitoring.dashboards.list",
    "monitoring.dashboards.get",
  ]
}
