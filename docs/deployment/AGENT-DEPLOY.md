# Deploying the agent tier (Vertex AI Agent Engine)

The agent reasoning engines are **not** deployed by the validated platform
(see DEPLOYMENT-LOG §11 D). This is the one-step-away procedure for when the
agents are built out. It is **billable** (Gemini tokens once invoked) and uses a
**Preview** API — treat a deploy as a deliberate, reviewed action.

## Prerequisites (in order)

1. **Implement the agent builders.** `build_<agent>()` in `agents/aop_<agent>/agent.py`
   currently raises `NotImplementedError` — they are skeleton ADK 2.1
   WorkflowAgent graphs. A deploy fails fast until these are wired. This is the
   real blocker; everything below is ready.
2. **Pick a supported region.** Agent Engine is region-limited and **does not
   include europe-west2** (the platform's default). Use e.g. `us-central1` or
   `europe-west1` — confirm against the Vertex AI generative-AI **locations**
   docs. `deploy.py` refuses europe-west2. If EU residency matters, this forces a
   split-region design (agents in a supported EU region; platform in europe-west2).
3. **Staging bucket.** Create a GCS bucket for the SDK to upload the packaged
   agent (`--staging-bucket gs://<project>-agent-staging`). Provision it in
   Terraform for repeatability.
4. **Per-agent service accounts** (`sa-<agent>`) must exist — created by the
   Terraform agent module (`modules/agent-runtime` or `modules/agents/*`).
5. **APIs:** `aiplatform.googleapis.com` (enabled by foundation) + the
   role-target APIs for the agent tier listed in `REQUIRED-APIS.md`.

## Path A — SDK (recommended): `agents/deployment/deploy.py`

Dry-run by default; `--execute` performs the billable deploy.

```bash
cd agents
# Plan only (no cost):
uv run python deployment/deploy.py --agent orchestrator \
  --project <project> --region us-central1 --env prod

# Deploy (billable, Preview):
uv run python deployment/deploy.py --agent orchestrator \
  --project <project> --region us-central1 --env prod \
  --execute --staging-bucket gs://<project>-agent-staging
```

`deploy.py` calls `vertexai.agent_engines.create(agent_engine=build_<agent>(settings),
requirements=[...], extra_packages=["aop_common", "aop_<agent>"], service_account=sa-<agent>@…)`.
Confirm the `create()` signature against the installed `google-cloud-aiplatform`
/ `google-adk` 2.1.x before first use. Repeat per agent (orchestrator, sre,
devsecops, platform, finops).

## Path B — Terraform: `modules/agents/_base` (or `agent-runtime`)

The `google_vertex_ai_reasoning_engine` resource takes
`package_pickle_gcs_uri` (default placeholder `gs://REPLACE_BUCKET/<slug>/agent.pkl`,
which the `_base` `check` block rejects). Produce the agent package with the
Vertex AI SDK packaging, upload it to GCS, then set:

```hcl
module "agent_orchestrator" {
  source                 = "../../modules/agents/orchestrator"
  # ...
  package_pickle_gcs_uri = "gs://<project>-agent-staging/orchestrator/agent.pkl"
}
```

Set the env root's region to a supported Agent Engine region for these modules.
`deletion_policy_prevent = true` in prod blocks reasoning-engine destruction
(flip it in a dedicated PR before any teardown).

## Cost

Negligible at rest; **Gemini tokens dominate once agents are invoked**
(~$58/mo dev light, up to ~$690/mo heavy — see `COST-ESTIMATE.md`). The
$20/mo budget alert covers the platform; raise it before enabling busy agents.

## Teardown

Path A: `agent_engines.delete()` per agent (or via the console). Path B:
`terraform destroy` after setting `deletion_policy_prevent = false`. Remove the
staging bucket contents afterwards.
