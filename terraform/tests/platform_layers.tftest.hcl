# Tests for the platform-layer modules — foundation, eventing, governance,
# observability, action-broker, slack-notifier, agent-runtime (legacy).
# Each run is plan-only; providers are scoped to the test file.
#
# Only `agent-runtime` requires google-beta; every other legacy module is
# google-only. The `providers = { ... }` map in each run reflects that.

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
# foundation
# ---------------------------------------------------------------------------

run "foundation_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/foundation"
  }

  variables {
    project_id               = "ops-agents-dev"
    region                   = "europe-west2"
    env                      = "dev"
    essential_contacts_email = "platform-owner@example.com"
  }
}

run "foundation_accepts_staging" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/foundation"
  }

  variables {
    project_id               = "ops-agents-stg"
    region                   = "europe-west2"
    env                      = "staging"
    essential_contacts_email = "platform-staging@example.com"
  }
}

run "foundation_rejects_unknown_env" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/foundation"
  }

  variables {
    project_id               = "ops-agents-dev"
    region                   = "europe-west2"
    env                      = "production"
    essential_contacts_email = "platform-owner@example.com"
  }

  expect_failures = [var.env]
}

# ---------------------------------------------------------------------------
# eventing
# ---------------------------------------------------------------------------

run "eventing_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/eventing"
  }

  variables {
    project_id          = "ops-agents-dev"
    env                 = "dev"
    region              = "europe-west2"
    audit_bq_dataset_id = "audit_logs"
    # plan-only/no-creds: the BQ subscription's data.google_project read needs
    # live API access, so disable it here (covered by the live deploy instead).
    enable_bq_audit_subscription = false
  }
}

run "eventing_accepts_staging" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/eventing"
  }

  variables {
    project_id                   = "ops-agents-stg"
    env                          = "staging"
    region                       = "europe-west2"
    audit_bq_dataset_id          = "audit_logs"
    enable_bq_audit_subscription = false
  }
}

# ---------------------------------------------------------------------------
# governance
# ---------------------------------------------------------------------------

run "governance_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/governance"
  }

  variables {
    project_id                    = "ops-agents-dev"
    env                           = "dev"
    region                        = "europe-west2"
    audit_bq_dataset_id           = "audit_logs"
    scc_notification_pubsub_topic = "projects/ops-agents-dev/topics/ops.signals"
  }
}

# ---------------------------------------------------------------------------
# observability
# ---------------------------------------------------------------------------

run "observability_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/observability"
  }

  variables {
    project_id                 = "ops-agents-dev"
    env                        = "dev"
    region                     = "europe-west2"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    slack_auth_token           = "xoxb-test-token"
    slack_workspace_id         = "TWORKSPACE0"
    slack_channel_incidents    = "#ops-incidents"
    slack_channel_security     = "#ops-security"
    broker_url                 = "https://broker.example.com"
    notifier_url               = "https://notifier.example.com"
  }
}

# ---------------------------------------------------------------------------
# action-broker
# ---------------------------------------------------------------------------

run "action_broker_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/action-broker"
  }

  variables {
    project_id                     = "ops-agents-dev"
    env                            = "dev"
    region                         = "europe-west2"
    container_image                = "europe-west2-docker.pkg.dev/ops-agents-dev/aop-containers/action-broker:test"
    ops_actions_approved_topic_id  = "projects/ops-agents-dev/topics/ops.actions.approved"
    ops_actions_requested_topic_id = "projects/ops-agents-dev/topics/ops.actions.requested"
    ops_actions_executed_topic_id  = "projects/ops-agents-dev/topics/ops.actions.executed"
    ops_audit_topic_id             = "projects/ops-agents-dev/topics/ops.audit"
  }
}

run "action_broker_accepts_workflows_pattern" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/action-broker"
  }

  variables {
    project_id                         = "ops-agents-dev"
    env                                = "prod"
    region                             = "europe-west2"
    container_image                    = "europe-west2-docker.pkg.dev/ops-agents-dev/aop-containers/action-broker:1.0"
    ops_actions_approved_topic_id      = "projects/ops-agents-dev/topics/ops.actions.approved"
    ops_actions_requested_topic_id     = "projects/ops-agents-dev/topics/ops.actions.requested"
    ops_actions_executed_topic_id      = "projects/ops-agents-dev/topics/ops.actions.executed"
    ops_audit_topic_id                 = "projects/ops-agents-dev/topics/ops.audit"
    workflows_invoker_resource_pattern = "aop-"
    min_instance_count                 = 1
  }
}

# ---------------------------------------------------------------------------
# slack-notifier
# ---------------------------------------------------------------------------

run "slack_notifier_plans_clean" {
  command = plan
  providers = {
    google = google
  }
  module {
    source = "../modules/slack-notifier"
  }

  variables {
    project_id                    = "ops-agents-dev"
    env                           = "dev"
    region                        = "europe-west2"
    container_image               = "europe-west2-docker.pkg.dev/ops-agents-dev/aop-containers/slack-notifier:test"
    ops_notifications_topic_id    = "projects/ops-agents-dev/topics/ops.notifications"
    ops_actions_approved_topic_id = "projects/ops-agents-dev/topics/ops.actions.approved"
  }
}

# ---------------------------------------------------------------------------
# agent-runtime (legacy — needs google-beta for the Memory Bank variant)
# ---------------------------------------------------------------------------

run "legacy_agent_runtime_plans_clean" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agent-runtime"
  }

  variables {
    project_id                 = "ops-agents-dev"
    env                        = "dev"
    region                     = "europe-west2"
    ops_signals_topic_id       = "projects/ops-agents-dev/topics/ops.signals"
    ops_findings_topic_id      = "projects/ops-agents-dev/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-dev/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-dev/topics/ops.audit"
  }
}

run "legacy_agent_runtime_accepts_staging" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agent-runtime"
  }

  variables {
    project_id                 = "ops-agents-stg"
    env                        = "staging"
    region                     = "europe-west2"
    ops_signals_topic_id       = "projects/ops-agents-stg/topics/ops.signals"
    ops_findings_topic_id      = "projects/ops-agents-stg/topics/ops.findings"
    ops_notifications_topic_id = "projects/ops-agents-stg/topics/ops.notifications"
    ops_audit_topic_id         = "projects/ops-agents-stg/topics/ops.audit"
  }
}
