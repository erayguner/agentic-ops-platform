# module/agent-runtime

Provisions the five AOP agents on Vertex AI Agent Engine (reasoning engines) plus their dedicated service accounts and read-only IAM grants.

## Resources created

- **5 service accounts** — `sa-orchestrator`, `sa-sre`, `sa-devsecops`, `sa-platform`, `sa-finops`.
- **IAM bindings** — read-only grants per DESIGN-REVIEW §5.3. No write IAM on any agent SA.
- **5 reasoning engines** — one per agent. `agent_framework = "google-adk"`; `deletion_policy` driven by `deletion_policy_prevent` variable (defaults `PREVENT` in prod).
- **Memory Bank skeleton** — one `google_vertex_ai_reasoning_engine` using `provider = google-beta` for the `context_spec` block. Annotated with an inline comment explaining the beta requirement and a TODO for when the field graduates to GA.

## Beta provider usage

The `context_spec` block on `google_vertex_ai_reasoning_engine` is only available in `hashicorp/google-beta`. Every resource using `provider = google-beta` carries an inline comment in `main.tf`. Remove `provider = google-beta` once `context_spec` reaches the stable provider.

## Package URIs

`pickle_object_gcs_uri` values are placeholders (`gs://REPLACE_BUCKET/...`). Replace with real GCS URIs after the ADK agent packages are built by CI.

## Inputs

| Name | Type | Default | Required |
|------|------|---------|----------|
| project_id | string | — | yes |
| env | string | — | yes |
| region | string | europe-west2 | no |
| deletion_policy_prevent | bool | false | no |
| ops_signals_topic_id | string | — | yes |
| ops_findings_topic_id | string | — | yes |
| ops_notifications_topic_id | string | — | yes |
| container_image_* | string | placeholder | no |

## Outputs

All SA emails and reasoning engine resource IDs. See `outputs.tf`.
