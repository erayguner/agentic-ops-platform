# Slack-notifier

Cloud Run service that receives `OpsNotification v1` events from the
`ops.notifications` Pub/Sub topic, renders them to Slack Block Kit, and posts
them to the appropriate channel via `chat.postMessage`. Also handles Slack
interactivity (Approve / Reject buttons) and publishes `ActionApproval v1` to
`ops.actions.approved`.

> **Python packaging is managed by [uv](https://docs.astral.sh/uv/) — not pip.**

## Architecture

```
ops.notifications  →  POST /pubsub/push  →  notifier.py
                                            ├── blockkit.py    (render)
                                            ├── redaction.py   (sanitise)
                                            └── Slack chat.postMessage

Slack Interactivity  →  POST /slack/interactivity
                         ├── signature.py       (HMAC-SHA256 verify)
                         ├── interactivity.py   (resolve user, build ActionApproval)
                         └── ops.actions.approved  (Pub/Sub publish)
```

## Set up the dev environment

```bash
cd services/slack-notifier
uv sync                  # creates .venv/, installs deps from uv.lock
```

Bump the lockfile after editing `pyproject.toml`:

```bash
uv lock
```

## Environment variables

| Variable               | Default          | Description                                                                                          |
| ---------------------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| `LIVE_SLACK_ENABLED`   | `false`          | When `false`, log rendered Block Kit JSON instead of calling Slack or Pub/Sub                        |
| `SLACK_BOT_TOKEN`      | _(required live)_| `xoxb-...` OAuth token; from Secret Manager secret `slack-oauth-token`                               |
| `SLACK_SIGNING_SECRET` | _(required)_     | From Secret Manager secret `slack-signing-secret`; used to verify interactivity requests             |
| `PUBSUB_PUSH_TOKEN`    | `""`             | Shared secret appended as `?token=` in the push subscription URL                                     |
| `GCP_PROJECT_ID`       | `ops-agents-dev` | Target project for Pub/Sub publish calls                                                             |
| `PORT`                 | `8080`           | Injected by Cloud Run                                                                                |

## Channel routing

| Domain                  | Severity            | Channel          |
| ----------------------- | ------------------- | ---------------- |
| `devsecops`             | any                 | `#ops-security`  |
| `finops`                | any                 | `#ops-finops`    |
| `platform`              | critical / high     | `#ops-incidents` |
| `platform`              | medium / low / info | `#ops-platform`  |
| `sre`, `orchestrator`   | any                 | `#ops-incidents` |
| eval-related signals    | —                   | `#ops-eval`      |
| Tier-2 audit announcements | —                | `#ops-audit`     |

> Channel discipline is enforced in `blockkit.resolve_channel()`.
> Changing the mapping requires a code change and review, not a runtime config.

## Run locally (dry-run, no real Slack calls)

```bash
LIVE_SLACK_ENABLED=false \
SLACK_SIGNING_SECRET=test \
  uv run uvicorn main:app --reload --port 8080
```

All Slack and Pub/Sub calls are replaced with log output at `INFO` level.

## Build the container

Build context is **this service's directory**:

```bash
docker build -t aop/slack-notifier services/slack-notifier
```

The Dockerfile uses uv for dependency resolution (no pip). It expects
`pyproject.toml` and `uv.lock` in the build context — commit both.

## Deploy

```bash
gcloud builds submit --tag europe-west2-docker.pkg.dev/ops-agents-prod/aop-containers/slack-notifier:$SHA \
    services/slack-notifier

gcloud run deploy slack-notifier \
  --image europe-west2-docker.pkg.dev/ops-agents-prod/aop-containers/slack-notifier:$SHA \
  --region europe-west2 \
  --service-account sa-slack-notifier@ops-agents-prod.iam.gserviceaccount.com \
  --set-secrets SLACK_BOT_TOKEN=slack-oauth-token:latest,SLACK_SIGNING_SECRET=slack-signing-secret:latest \
  --set-env-vars LIVE_SLACK_ENABLED=true,GCP_PROJECT_ID=ops-agents-prod \
  --no-allow-unauthenticated
```

The Pub/Sub push subscription is managed by the `terraform/modules/slack-notifier/`
module, which configures the audience, `oidc_token`, and `?token=` parameter.
