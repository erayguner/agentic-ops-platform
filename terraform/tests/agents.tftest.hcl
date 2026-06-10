# Per-agent module tests.
#
# Each `run` block must declare its own providers (see framework.tftest.hcl
# for the rationale). Plan-only — no API calls are made.

provider "google" {
  project      = "test-project"
  region       = "europe-west2"
  access_token = "fake-token-plan-only-never-used-against-the-api"
}

provider "google-beta" {
  project      = "test-project"
  region       = "europe-west2"
  access_token = "fake-token-plan-only-never-used-against-the-api"
}

# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------

run "orchestrator_plans_clean_with_minimum_inputs" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/orchestrator"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "dev"
    ops_signals_topic_id       = "projects/ops-agents-dev/topics/ops.signals"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/orchestrator/agent.pkl"
  }
}

run "orchestrator_rejects_unknown_env" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/orchestrator"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "production"
    ops_signals_topic_id       = "projects/ops-agents-dev/topics/ops.signals"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/orchestrator/agent.pkl"
  }

  expect_failures = [var.env]
}

# ---------------------------------------------------------------------------
# sre
# ---------------------------------------------------------------------------

run "sre_plans_clean_with_minimum_inputs" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/sre"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "dev"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/sre/agent.pkl"
  }
}

run "sre_accepts_schedule" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/sre"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "staging"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/sre/agent.pkl"
    schedule = {
      cron       = "*/15 * * * *"
      target_uri = "https://example.com/sweep"
    }
  }
}

# ---------------------------------------------------------------------------
# devsecops
# ---------------------------------------------------------------------------

run "devsecops_plans_clean" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/devsecops"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "dev"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/devsecops/agent.pkl"
  }
}

# ---------------------------------------------------------------------------
# platform
# ---------------------------------------------------------------------------

run "platform_plans_clean" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/platform"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "dev"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/platform/agent.pkl"
  }
}

# ---------------------------------------------------------------------------
# finops
# ---------------------------------------------------------------------------

run "finops_plans_clean_with_dataset_scope" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/finops"
  }

  variables {
    project_id                   = "ops-agents-dev"
    region                       = "europe-west2"
    env                          = "dev"
    ops_findings_topic_id        = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id   = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id           = "projects/ops-agents-dev/topics/ops.audit"
    billing_export_bq_dataset_id = "billing_export"
    package_pickle_gcs_uri       = "gs://test-bucket/finops/agent.pkl"
  }
}

run "finops_plans_clean_in_dev_without_dataset_scope" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/finops"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "dev"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/finops/agent.pkl"
  }
}

# ---------------------------------------------------------------------------
# decommission
# ---------------------------------------------------------------------------

run "decommission_plans_clean_with_minimum_inputs" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/decommission"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "dev"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/decommission/agent.pkl"
  }
}

run "decommission_sa_is_read_only" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/decommission"
  }

  variables {
    project_id                 = "ops-agents-dev"
    region                     = "europe-west2"
    env                        = "prod"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri     = "gs://test-bucket/decommission/agent.pkl"
    deletion_policy_prevent    = true
  }

  # Every granted role must be read-only — assert the module exposes only those.
  assert {
    condition = alltrue([
      for r in output.predefined_roles : can(regex("(?i)(viewer|reader|browser)$", r))
    ])
    error_message = "Decommission SA must hold only read-only roles."
  }
}
