# Action Broker

Cloud Run service that is the **only execution surface** for agent write
actions in the Agentic Operations Platform. No specialist agent holds write
IAM; all writes flow through this service under policy control.

> **Python packaging is managed by [uv](https://docs.astral.sh/uv/) — not pip.**

## Architecture

```
Agent (MCP tool call)
  └── POST /mcp/tools/call  {name: "propose_action", ...}
       ├── ID-token verification        (sa-* must present OIDC token)
       ├── broker.propose_action()
       │    ├── idempotency check       (Firestore)
       │    ├── executor.validate()
       │    ├── PolicyEngine.decide()
       │    ├── Tier ≤ 2  → execute directly
       │    └── Tier ≥ 3  → publish ops.actions.requested → await Slack approval
       └── return {status, action_id, ...}

Slack Approve / Reject
  └── POST /pubsub/approved  (ops.actions.approved push)
       └── broker.on_approval()
            └── re-fetch action request → execute → verify → audit
                                                       └── rollback on failure
```

## MCP tools exposed

| Tool               | Description                                                                                                   |
| ------------------ | ------------------------------------------------------------------------------------------------------------- |
| `propose_action`   | Main entry point — validate, policy-check, auto-approve (Tier ≤ 2) or queue for approval (Tier ≥ 3)            |
| `request_approval` | Query pending approval status                                                                                  |
| `execute`          | Execute a pre-approved action (used for Tier-2 auto-approve override)                                          |
| `rollback`         | Roll back a completed action                                                                                   |
| `status`           | Return current action status by ID                                                                             |

## Security model

- The Broker runs as `sa-action-broker` — **no broad write IAM**.
- For each execution, it mints a short-lived token (≤ 1 h) for the
  per-action-class SA via `iam.serviceAccountTokenCreator`
  (`impersonation.py`).
- Per-action-class SAs carry only the minimum role scoped by Principal
  Access Boundary.
- The broker is the **only** writer; agents are read-only on GCP APIs.

## Set up the dev environment

```bash
cd services/action-broker
uv sync                  # creates .venv/, installs deps from uv.lock
```

Bump the lockfile after editing `pyproject.toml`:

```bash
uv lock
```

## Environment variables

| Variable                   | Default          | Description                                                                                                |
| -------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------- |
| `LIVE_MODE`                | `false`          | When `false`, executors raise `NotImplementedError`; event chains (Pub/Sub, audit, idempotency) log-only   |
| `GCP_PROJECT_ID`           | `ops-agents-dev` | Target GCP project                                                                                         |
| `PUBSUB_PUSH_TOKEN`        | `""`             | Shared secret for push subscription URL validation                                                         |
| `APPROVAL_WINDOW_MINUTES`  | `15`             | Slack approval expiry window                                                                               |
| `POLICY_FILE`              | `policy/action_classes.yaml` | Path to the policy file (autonomy tiers + bounds per action class × env)                       |
| `PORT`                     | `8080`           | Injected by Cloud Run                                                                                      |

## Policy

Autonomy tiers and bounds are declared in `policy/action_classes.yaml`.
Changing a tier requires a PR with **≥ 2 reviewers** and a passing policy
unit test (see `tests/`).

## Run locally (dry-run, no real GCP / Slack calls)

```bash
LIVE_MODE=false \
GCP_PROJECT_ID=ops-agents-dev \
  uv run uvicorn main:app --reload --port 8080
```

All write APIs are replaced with log output at `INFO` level; the
idempotency Firestore client is stubbed.

## Build the container

Build context is **this service's directory**:

```bash
docker build -t aop/action-broker services/action-broker
```

The Dockerfile uses uv for dependency resolution (no pip). It expects
`pyproject.toml` and `uv.lock` in the build context — commit both.

## Deploy

```bash
gcloud builds submit --tag europe-west2-docker.pkg.dev/ops-agents-prod/aop-containers/action-broker:$SHA \
    services/action-broker

gcloud run deploy action-broker \
  --image europe-west2-docker.pkg.dev/ops-agents-prod/aop-containers/action-broker:$SHA \
  --region europe-west2 \
  --service-account sa-action-broker@ops-agents-prod.iam.gserviceaccount.com \
  --set-env-vars LIVE_MODE=true,GCP_PROJECT_ID=ops-agents-prod \
  --no-allow-unauthenticated
```

The service **must not** be public (`--no-allow-unauthenticated`). Agents
call it with their OIDC token; the Pub/Sub push subscription uses the
signed OIDC token path configured in the
`terraform/modules/action-broker/` module.
