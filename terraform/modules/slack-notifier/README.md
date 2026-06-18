# module/slack-notifier

Provisions the Slack Notifier Cloud Run service — renders `OpsNotification` events as Slack Block Kit messages and handles interactivity (approve/reject buttons).

## Resources created

- **`sa-slack-notifier`** — Cloud Run service identity.
- **Secrets** — `slack-oauth-token` and `slack-signing-secret` in Secret Manager. Values must be populated out-of-band (CI or manual `gcloud secrets versions add`). Never commit real values.
- **Pub/Sub push subscription** — `ops.notifications.notifier-push` → Cloud Run `/pubsub/push` with OIDC auth.
- **IAM** — notifier reads both secrets; publishes to `ops.actions.approved` (for approve/reject button responses).
- **`google_cloud_run_v2_service`** — `slack-notifier` with env vars for channel routing and secret refs.

## Secrets population (after `terraform apply`)

```bash
echo -n "xoxb-..." | gcloud secrets versions add slack-oauth-token \
  --data-file=- --project=ops-agents-dev

echo -n "abc123..." | gcloud secrets versions add slack-signing-secret \
  --data-file=- --project=ops-agents-dev
```

## Inputs

| Name                          | Type   | Default        | Required |
| ----------------------------- | ------ | -------------- | -------- |
| project_id                    | string | —              | yes      |
| env                           | string | —              | yes      |
| ops_notifications_topic_id    | string | —              | yes      |
| ops_actions_approved_topic_id | string | —              | yes      |
| slack_channel_incidents       | string | #ops-incidents | no       |
| slack_channel_security        | string | #ops-security  | no       |
| slack_channel_finops          | string | #ops-finops    | no       |
| slack_channel_platform        | string | #ops-platform  | no       |
| container_image               | string | placeholder    | no       |
| min_instance_count            | number | 0              | no       |

## Outputs

| Name                           | Description                  |
| ------------------------------ | ---------------------------- |
| service_url                    | Cloud Run service URL        |
| sa_slack_notifier_email        | Notifier SA email            |
| slack_oauth_token_secret_id    | Secret ID for OAuth token    |
| slack_signing_secret_secret_id | Secret ID for signing secret |
