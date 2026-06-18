# `agents/decommission` module

Provisions the **Decommission Agent** — the project-closure specialist — on top
of the shared [`agents/_base`](../_base) module.

## What it creates

- A dedicated, **read-only** service account `sa-decommission@<project>` with:
  - `roles/cloudasset.viewer` — live estate inventory (Cloud Asset Inventory)
  - `roles/resourcemanager.projectViewer` — project / ancestry metadata
  - `roles/monitoring.viewer`, `roles/logging.viewer` — activity / idle signals
  - `roles/recommender.viewer` — idle-resource recommendations
  - `roles/mcp.toolUser` and `pubsub.publisher` on `ops.audit` (from `_base`)
- A `google_vertex_ai_reasoning_engine` for the agent.
- An optional Cloud Scheduler trigger for a periodic closure-readiness sweep.

## Why no write IAM

The decommission agent is the one agent whose mandate is destruction, so it is
the most important one to keep powerless. It holds **no delete/write role**.
Every teardown is proposed to the **Action Broker**, which policy-gates the
action (`terraform.destroy_target` / `decommission.delete_resource`), routes prod
destroys to human approval (2 approvers), enforces a `max_blast_radius` bound,
and only then runs the actual destroy. A `check` block in `main.tf` fails the
plan if any granted role is not read-only.

## Usage

```hcl
module "decommission_agent" {
  source = "../../modules/agents/decommission"

  project_id                 = "ops-agents-dev"
  region                     = "europe-west2"
  env                        = "dev"
  ops_findings_topic_id      = module.eventing.findings_topic_id
  ops_notifications_topic_id = module.eventing.notifications_topic_id
  ops_audit_topic_id         = module.eventing.audit_topic_id
  package_pickle_gcs_uri     = "gs://ops-agents-dev-agent-staging/decommission/agent.pkl"

  # Optional: a daily plan-only closure sweep.
  schedule = {
    cron       = "0 6 * * *"
    target_uri = "https://decommission-agent-xxxx-nw.a.run.app/sweep"
  }
}
```

In `prod`, set `deletion_policy_prevent = true`.
