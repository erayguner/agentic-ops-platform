# Terraform native tests for the AOP framework. Each `run` block runs in
# plan-only mode (`command = plan`) so no GCP API calls are made. Tests
# assert on input validation, variable propagation, and `check` blocks.

# ---------------------------------------------------------------------------
# Variable validation — agent_slug, env, project_id
# ---------------------------------------------------------------------------

run "agent_base_rejects_invalid_slug" {
  command = plan

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

run "composition_rejects_invalid_env" {
  command = plan

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

  module {
    source = "../modules/aop-platform"
  }

  variables {
    project_id = "X"
    env        = "dev"
  }

  expect_failures = [var.project_id]
}

run "schedule_requires_both_cron_and_target_uri" {
  command = plan

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
