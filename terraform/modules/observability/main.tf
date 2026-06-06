locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "observability"
      managed_by = "terraform"
    },
    var.labels,
  )

  # Alert delivery channels: the Pub/Sub channel is always present; the native
  # Slack channel is added only when enabled (it requires a live Slack token,
  # which a validation/no-token deploy will not have).
  alert_notification_channels = compact(concat(
    var.enable_slack_notification_channel ? [google_monitoring_notification_channel.slack_primary[0].id] : [],
    [google_monitoring_notification_channel.pubsub_redundant.id],
  ))
}

# ---------------------------------------------------------------------------
# Notification channel 1 — native Slack (primary)
# auth_token_wo is a write-only attribute; pair with auth_token_wo_version.
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "slack_primary" {
  # Native Slack channels are verified against the live token at create time;
  # gate off for token-less / validation deploys. Alerts still deliver via the
  # Pub/Sub channel. Default true preserves the full posture in real envs.
  count = var.enable_slack_notification_channel ? 1 : 0

  project      = var.project_id
  display_name = "AOP Slack — ${var.slack_channel_incidents}"
  type         = "slack"

  # channel_name is the Slack channel to post to (e.g. "#ops-incidents").
  # auth_token_wo (write-only, Terraform >= 1.11) holds the OAuth bot token;
  # it is never written to state. Increment auth_token_wo_version to rotate
  # the token without drift between the config version and state.
  labels = {
    channel_name = var.slack_channel_incidents
  }

  sensitive_labels {
    auth_token_wo         = var.slack_auth_token
    auth_token_wo_version = var.slack_auth_token_version
  }

  user_labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Notification channel 2 — Pub/Sub (redundant path for Critical alerts)
# Slack, Cloud Mobile App, and Webhooks share one delivery service;
# a Pub/Sub channel provides an independent delivery path.
# ---------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "pubsub_redundant" {
  project      = var.project_id
  display_name = "AOP Pub/Sub redundant — Critical alerts"
  type         = "pubsub"

  labels = {
    topic = var.ops_notifications_topic_id
  }

  user_labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Alert policy 1 — Agent down (synthetic ping stops responding)
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "agent_down" {
  # References the aiplatform ReasoningEngine system metric, which only exists
  # once an agent (reasoning engine) is deployed and emitting. Gate off when no
  # agents are running, else alert creation 404s on the missing metric type.
  count = var.enable_agent_engine_alerts ? 1 : 0

  project      = var.project_id
  display_name = "AOP — Agent down"
  combiner     = "OR"

  conditions {
    display_name = "Agent Engine request count drops to zero"
    condition_threshold {
      filter          = "resource.type = \"aiplatform.googleapis.com/ReasoningEngine\" AND metric.type = \"aiplatform.googleapis.com/prediction/online/request_count\""
      duration        = "300s" # 5 minutes
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = local.alert_notification_channels

  alert_strategy {
    auto_close = "1800s"
  }

  user_labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Alert policy 2 — Decision latency p95 > 60 s
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "decision_latency_p95" {
  # References the aiplatform ReasoningEngine system metric (see agent_down).
  count = var.enable_agent_engine_alerts ? 1 : 0

  project      = var.project_id
  display_name = "AOP — Decision latency p95 > 60 s"
  combiner     = "OR"

  conditions {
    display_name = "Agent Engine p95 latency exceeds 60 s"
    condition_threshold {
      filter          = "resource.type = \"aiplatform.googleapis.com/ReasoningEngine\" AND metric.type = \"aiplatform.googleapis.com/prediction/online/request_latencies\""
      duration        = "900s" # 15 minutes rolling
      comparison      = "COMPARISON_GT"
      threshold_value = 60000 # milliseconds
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_PERCENTILE_95"
      }
    }
  }

  notification_channels = local.alert_notification_channels

  alert_strategy {
    auto_close = "3600s"
  }

  user_labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Alert policy 3 — Action rollback rate > 5% (7-day window)
# Based on custom log-based metric defined below
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "action_rollback_rate" {
  project      = var.project_id
  display_name = "AOP — Action rollback rate > 5%"
  combiner     = "OR"

  conditions {
    display_name = "Action rollback log-based metric exceeds 5% threshold"
    condition_threshold {
      filter          = "metric.type = \"logging.googleapis.com/user/aop_action_rollback_count\" AND resource.type = \"cloud_run_revision\""
      duration        = "600s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = local.alert_notification_channels

  alert_strategy {
    auto_close = "604800s" # 7 days
  }

  user_labels = local.common_labels

  # The condition filter references this log-based metric by type (not a
  # resource reference), so Terraform cannot infer the dependency. Make it
  # explicit: the metric must be created before this policy and destroyed
  # after it (else metric deletion fails: "still used in an alerting policy").
  depends_on = [google_logging_metric.action_rollback_count]
}

# ---------------------------------------------------------------------------
# Log-based metric 1 — Token spend (extracted from ADK OTel agent logs)
# ---------------------------------------------------------------------------

resource "google_logging_metric" "token_spend" {
  project     = var.project_id
  name        = "aop_token_spend_total"
  description = "Total LLM tokens consumed by AOP agents, extracted from ADK OTel structured logs."
  filter      = "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\" AND jsonPayload.model.tokens_in > 0"

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "DISTRIBUTION" # a value_extractor is only valid on DISTRIBUTION metrics
    unit         = "1"
    display_name = "AOP token spend"
    labels {
      key         = "agent_identity"
      value_type  = "STRING"
      description = "SA email or SPIFFE identity of the emitting agent."
    }
  }

  label_extractors = {
    agent_identity = "EXTRACT(jsonPayload.agent_identity)"
  }

  value_extractor = "EXTRACT(jsonPayload.model.tokens_in)"

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 2.0
      scale              = 1.0
    }
  }
}

# ---------------------------------------------------------------------------
# Log-based metric 2 — Policy denials (Action Broker policy_decision=denied)
# ---------------------------------------------------------------------------

resource "google_logging_metric" "policy_denials" {
  project     = var.project_id
  name        = "aop_policy_denial_count"
  description = "Count of Action Broker policy decisions where outcome=denied. Spike may indicate misconfiguration or attack."
  filter      = "resource.type=\"cloud_run_revision\" AND jsonPayload.policy_decision.outcome=\"denied\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "AOP policy denials"
    labels {
      key         = "action_class"
      value_type  = "STRING"
      description = "Action class that was denied."
    }
  }

  label_extractors = {
    action_class = "EXTRACT(jsonPayload.action_class)"
  }
}

# ---------------------------------------------------------------------------
# Log-based metric 3 — Action rollback count (for rollback-rate alert)
# ---------------------------------------------------------------------------

resource "google_logging_metric" "action_rollback_count" {
  project     = var.project_id
  name        = "aop_action_rollback_count"
  description = "Count of Action Broker executions that triggered a rollback (outcome.rollback=true)."
  filter      = "resource.type=\"cloud_run_revision\" AND jsonPayload.outcome.status=\"rolled_back\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "AOP action rollback count"
  }
}

# ---------------------------------------------------------------------------
# Log-based metric 4 — Alert dwell time (Zero Trust "Measure what matters")
# Distribution of seconds between anomaly occurrence and first-pass triage,
# extracted from the TriageDisposition emitted by aop_common/triage.py.
# Dwell time is the leading detection-speed indicator; target < 1h for critical.
# ---------------------------------------------------------------------------

resource "google_logging_metric" "alert_dwell_seconds" {
  project     = var.project_id
  name        = "aop_alert_dwell_seconds"
  description = "Seconds from anomaly occurrence to first-pass triage (dwell time), from ops.triage_disposition.v1."
  filter      = "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\" AND jsonPayload.schema=\"ops.triage_disposition.v1\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "DISTRIBUTION"
    unit         = "s"
    display_name = "AOP alert dwell time"
    labels {
      key         = "severity"
      value_type  = "STRING"
      description = "Signal severity (info..critical)."
    }
    labels {
      key         = "disposition"
      value_type  = "STRING"
      description = "Triage disposition (auto_close, investigate, escalate, suppress_duplicate)."
    }
  }

  value_extractor = "EXTRACT(jsonPayload.dwell_seconds)"

  label_extractors = {
    severity    = "EXTRACT(jsonPayload.severity)"
    disposition = "EXTRACT(jsonPayload.disposition)"
  }

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 64
      growth_factor      = 1.4
      scale              = 1.0
    }
  }
}

# ---------------------------------------------------------------------------
# Log-based metric 5 — Triage coverage (count of triaged signals by route)
# coverage = sum(routed_to_human="true") / sum(all) — the fraction of alerts
# routed for human investigation rather than auto-closed/suppressed.
# ---------------------------------------------------------------------------

resource "google_logging_metric" "alert_triage_total" {
  project     = var.project_id
  name        = "aop_alert_triage_total"
  description = "Count of first-pass triage dispositions, labelled by route — the coverage denominator/numerator."
  filter      = "resource.type=\"aiplatform.googleapis.com/ReasoningEngine\" AND jsonPayload.schema=\"ops.triage_disposition.v1\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "AOP triage dispositions"
    labels {
      key         = "disposition"
      value_type  = "STRING"
      description = "Triage disposition."
    }
    labels {
      key         = "routed_to_human"
      value_type  = "STRING"
      description = "Whether the alert was routed for human investigation (coverage numerator)."
    }
  }

  label_extractors = {
    disposition     = "EXTRACT(jsonPayload.disposition)"
    routed_to_human = "EXTRACT(jsonPayload.routed_to_human)"
  }
}

# ---------------------------------------------------------------------------
# Alert policy 4 — Detection dwell p95 > 1 h for critical signals
# "Target detection within an hour for critical systems." Fires when the 95th
# percentile dwell time for critical-severity signals exceeds one hour.
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "detection_dwell_p95" {
  project      = var.project_id
  display_name = "AOP — Detection dwell p95 > 1h (critical)"
  combiner     = "OR"

  conditions {
    display_name = "Critical-severity dwell p95 exceeds 3600 s"
    condition_threshold {
      filter          = "metric.type = \"logging.googleapis.com/user/aop_alert_dwell_seconds\" AND resource.type = \"aiplatform.googleapis.com/ReasoningEngine\" AND metric.labels.severity = \"critical\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 3600
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }

  notification_channels = local.alert_notification_channels

  alert_strategy {
    auto_close = "86400s"
  }

  user_labels = local.common_labels

  # Explicit dependency on the referenced log-based metric (filter uses it by
  # type) so create/destroy ordering is correct.
  depends_on = [google_logging_metric.alert_dwell_seconds]
}

# ---------------------------------------------------------------------------
# Uptime check — action-broker
# ---------------------------------------------------------------------------

resource "google_monitoring_uptime_check_config" "action_broker" {
  project      = var.project_id
  display_name = "AOP action-broker liveness"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path           = "/healthz"
    port           = 443
    use_ssl        = true
    validate_ssl   = true
    request_method = "GET"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = replace(var.broker_url, "https://", "")
    }
  }

  selected_regions = ["USA", "EUROPE", "ASIA_PACIFIC"]
}

# ---------------------------------------------------------------------------
# Uptime check — slack-notifier
# ---------------------------------------------------------------------------

resource "google_monitoring_uptime_check_config" "slack_notifier" {
  project      = var.project_id
  display_name = "AOP slack-notifier liveness"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path           = "/healthz"
    port           = 443
    use_ssl        = true
    validate_ssl   = true
    request_method = "GET"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = replace(var.notifier_url, "https://", "")
    }
  }

  selected_regions = ["USA", "EUROPE", "ASIA_PACIFIC"]
}

# ---------------------------------------------------------------------------
# Monitored Service — action-broker (required before creating an SLO)
# google_monitoring_slo.service references this service's service_id.
# ---------------------------------------------------------------------------

resource "google_monitoring_custom_service" "action_broker" {
  project      = var.project_id
  service_id   = "aop-action-broker"
  display_name = "AOP Action Broker"

  user_labels = local.common_labels
}

# ---------------------------------------------------------------------------
# SLO — action-broker availability (windows-based, uptime check backed)
# ---------------------------------------------------------------------------

resource "google_monitoring_slo" "broker_availability" {
  # The good_total_ratio SLI below aggregates uptime_check/check_passed, a
  # GAUGE BOOL metric, which the API rejects with an ALIGN_DELTA aligner error.
  # A correct uptime-based availability SLO needs a reworked SLI; gate until then.
  count = var.enable_slo ? 1 : 0

  project      = var.project_id
  service      = google_monitoring_custom_service.action_broker.service_id
  slo_id       = "aop-broker-availability"
  display_name = "AOP Action Broker availability (99.5%)"
  goal         = 0.995

  rolling_period_days = 30

  windows_based_sli {
    window_period = "3600s"
    good_total_ratio_threshold {
      threshold = 0.995
      performance {
        good_total_ratio {
          good_service_filter  = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.action_broker.uptime_check_id}\""
          total_service_filter = "metric.type=\"monitoring.googleapis.com/uptime_check/request_count\" AND resource.type=\"uptime_url\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.action_broker.uptime_check_id}\""
        }
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Dashboard — ops-platform-overview (inline JSON)
# ---------------------------------------------------------------------------

resource "google_monitoring_dashboard" "ops_platform_overview" {
  project = var.project_id
  dashboard_json = jsonencode({
    displayName = "AOP — Platform Overview (${var.env})"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Agent Engine request count (all agents)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"aiplatform.googleapis.com/prediction/online/request_count\" AND resource.type=\"aiplatform.googleapis.com/ReasoningEngine\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
                plotType = "LINE"
              }]
              timeshiftDuration = "0s"
              yAxis             = { label = "req/s", scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Token spend by agent (delta/hr)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/aop_token_spend_total\""
                    aggregation = {
                      alignmentPeriod    = "3600s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.labels.agent_identity"]
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
              yAxis = { label = "tokens", scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Policy denials (delta/hr)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/aop_policy_denial_count\""
                    aggregation = {
                      alignmentPeriod  = "3600s"
                      perSeriesAligner = "ALIGN_DELTA"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { label = "denials", scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Action rollback count (delta/hr)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/aop_action_rollback_count\""
                    aggregation = {
                      alignmentPeriod  = "3600s"
                      perSeriesAligner = "ALIGN_DELTA"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { label = "rollbacks", scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Alert dwell p95 by severity (s)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/aop_alert_dwell_seconds\""
                    aggregation = {
                      alignmentPeriod    = "3600s"
                      perSeriesAligner   = "ALIGN_PERCENTILE_95"
                      crossSeriesReducer = "REDUCE_MAX"
                      groupByFields      = ["metric.labels.severity"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { label = "seconds", scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Triage coverage — routed vs total (delta/hr)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/aop_alert_triage_total\""
                    aggregation = {
                      alignmentPeriod    = "3600s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.labels.routed_to_human"]
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
              yAxis = { label = "dispositions", scale = "LINEAR" }
            }
          }
        }
      ]
    }
  })
}
