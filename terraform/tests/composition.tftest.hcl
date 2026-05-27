# Integration tests for the aop-platform composition module — verifies that
# different feature-flag combinations all plan successfully. Each enabled
# agent must supply a `package_pickle_gcs_uri` so the `_base` placeholder
# check does not fail the plan.

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

# Full-stack dev composition — every layer + every agent.
run "composition_full_dev_plans" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id               = "ops-agents-dev"
    env                      = "dev"
    region                   = "europe-west2"
    essential_contacts_email = "platform-owner@example.com"
    slack_auth_token         = "xoxb-test-token"
    slack_workspace_id       = "TWORKSPACE0"

    enabled_agents = {
      orchestrator = { package_pickle_gcs_uri = "gs://test/orchestrator.pkl" }
      sre          = { package_pickle_gcs_uri = "gs://test/sre.pkl" }
      devsecops    = { package_pickle_gcs_uri = "gs://test/devsecops.pkl" }
      platform     = { package_pickle_gcs_uri = "gs://test/platform.pkl" }
      finops       = { package_pickle_gcs_uri = "gs://test/finops.pkl" }
    }
  }
}

# Minimal SRE-only composition — disables broker, notifier, observability.
run "composition_minimal_sre_only_plans" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id               = "ops-agents-dev"
    env                      = "dev"
    region                   = "europe-west2"
    essential_contacts_email = "sre-oncall@example.com"

    enable_action_broker  = false
    enable_slack_notifier = false
    enable_observability  = false

    enabled_agents = {
      sre = {
        package_pickle_gcs_uri = "gs://test/sre.pkl"
        schedule = {
          cron       = "*/15 * * * *"
          target_uri = "https://sre-fanout.example.com/run"
        }
      }
    }
  }
}

# Staging — warm pools, no destroy lock.
run "composition_staging_plans" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id               = "ops-agents-stg"
    env                      = "staging"
    region                   = "europe-west2"
    essential_contacts_email = "platform-staging@example.com"
    slack_auth_token         = "xoxb-staging-token"
    slack_workspace_id       = "TWORKSPACESTG"

    finops_billing_export_bq_dataset_id = "billing_export"

    min_instance_count_broker   = 1
    min_instance_count_notifier = 1

    enabled_agents = {
      orchestrator = { package_pickle_gcs_uri = "gs://test/orchestrator.pkl" }
      sre          = { package_pickle_gcs_uri = "gs://test/sre.pkl" }
      devsecops    = { package_pickle_gcs_uri = "gs://test/devsecops.pkl" }
      platform     = { package_pickle_gcs_uri = "gs://test/platform.pkl" }
      finops = {
        package_pickle_gcs_uri = "gs://test/finops.pkl"
        schedule = {
          cron       = "0 6 * * *"
          target_uri = "https://finops-fanout-staging.example.com/run"
        }
      }
    }
  }
}

# Prod — locked-down posture.
run "composition_prod_locked_down_plans" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id               = "ops-agents-prd"
    env                      = "prod"
    region                   = "europe-west2"
    essential_contacts_email = "platform-prod@example.com"
    slack_auth_token         = "xoxb-prod-token"
    slack_workspace_id       = "TWORKSPACEPROD"

    container_image_action_broker  = "europe-west2-docker.pkg.dev/ops-agents-prd/aop-containers/action-broker:1.0"
    container_image_slack_notifier = "europe-west2-docker.pkg.dev/ops-agents-prd/aop-containers/slack-notifier:1.0"

    finops_billing_export_bq_dataset_id = "billing_export"

    min_instance_count_broker          = 1
    min_instance_count_notifier        = 1
    deletion_policy_prevent            = true
    workflows_invoker_resource_pattern = "aop-"

    enabled_agents = {
      orchestrator = {
        package_pickle_gcs_uri = "gs://test/orchestrator.pkl"
        enable_memory_bank     = true
      }
      sre       = { package_pickle_gcs_uri = "gs://test/sre.pkl" }
      devsecops = { package_pickle_gcs_uri = "gs://test/devsecops.pkl" }
      platform  = { package_pickle_gcs_uri = "gs://test/platform.pkl" }
      finops = {
        package_pickle_gcs_uri = "gs://test/finops.pkl"
        schedule = {
          cron       = "0 6 * * *"
          target_uri = "https://finops-fanout-prod.example.com/run"
        }
      }
    }
  }
}

# Subset selection — drop a key entirely, agent is not provisioned.
run "composition_drops_disabled_agents" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id               = "ops-agents-dev"
    env                      = "dev"
    region                   = "europe-west2"
    essential_contacts_email = "platform-owner@example.com"
    slack_auth_token         = "xoxb-test-token"

    enabled_agents = {
      orchestrator = { package_pickle_gcs_uri = "gs://test/orchestrator.pkl" }
      sre          = { enabled = true, package_pickle_gcs_uri = "gs://test/sre.pkl" }
      devsecops    = { enabled = false }
      # platform and finops omitted entirely
    }
  }
}
