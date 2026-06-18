# Composition-level tests for the AOP framework.
#
# When a `run` block uses `module { source = ... }` it swaps the root module
# and does NOT inherit providers from the test directory's .tf files. Provider
# blocks therefore live in the .tftest.hcl file itself, and each run block
# passes them through via `providers = { ... }`.
#
# `access_token` is a literal so the providers never attempt to load
# Application Default Credentials — tests run in plan-only mode, no API call
# is ever made.

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
# _base — variable validation
# ---------------------------------------------------------------------------

run "agent_base_rejects_invalid_slug" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/_base"
  }

  variables {
    project_id             = "ops-agents-dev"
    region                 = "europe-west2"
    env                    = "dev"
    agent_slug             = "INVALID--CAPITALS"
    agent_display_name     = "Bad Agent"
    agent_description      = "Should fail validation."
    ops_audit_topic_id     = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri = "gs://test-bucket/test/agent.pkl"
  }

  expect_failures = [var.agent_slug]
}

run "agent_base_rejects_owner_role" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/_base"
  }

  variables {
    project_id             = "ops-agents-dev"
    region                 = "europe-west2"
    env                    = "dev"
    agent_slug             = "test"
    agent_display_name     = "Test Agent"
    agent_description      = "Trying to grant owner."
    ops_audit_topic_id     = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri = "gs://test-bucket/test/agent.pkl"
    project_iam_roles      = ["roles/owner"]
  }

  expect_failures = [var.project_iam_roles]
}

run "agent_base_rejects_editor_role" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/_base"
  }

  variables {
    project_id             = "ops-agents-dev"
    region                 = "europe-west2"
    env                    = "dev"
    agent_slug             = "test"
    agent_display_name     = "Test Agent"
    agent_description      = "Trying to grant editor."
    ops_audit_topic_id     = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri = "gs://test-bucket/test/agent.pkl"
    project_iam_roles      = ["roles/viewer", "roles/editor"]
  }

  expect_failures = [var.project_iam_roles]
}

run "schedule_requires_both_cron_and_target_uri" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/agents/_base"
  }

  variables {
    project_id             = "ops-agents-dev"
    region                 = "europe-west2"
    env                    = "dev"
    agent_slug             = "test"
    agent_display_name     = "Test Agent"
    agent_description      = "Schedule missing target."
    ops_audit_topic_id     = "projects/ops-agents-dev/topics/ops.audit"
    package_pickle_gcs_uri = "gs://test-bucket/test/agent.pkl"
    schedule = {
      cron = "*/5 * * * *"
    }
  }

  expect_failures = [var.schedule]
}

# ---------------------------------------------------------------------------
# aop-platform — composition-level variable validation
# ---------------------------------------------------------------------------

run "composition_rejects_invalid_env" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id = "ops-agents-dev"
    env        = "production"
  }

  expect_failures = [var.env]
}

run "composition_rejects_invalid_agent_key" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id = "ops-agents-dev"
    env        = "dev"
    enabled_agents = {
      not_an_agent = {}
    }
  }

  expect_failures = [var.enabled_agents]
}

run "composition_rejects_invalid_project_id" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id = "X"
    env        = "dev"
  }

  expect_failures = [var.project_id]
}

run "composition_rejects_invalid_region" {
  command = plan
  providers = {
    google      = google
    google-beta = google-beta
  }
  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id = "ops-agents-dev"
    env        = "dev"
    region     = "NOT-A-REGION"
  }

  expect_failures = [var.region]
}
