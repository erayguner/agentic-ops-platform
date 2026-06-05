# module/agent-runtime

Provisions the five AOP agents on Vertex AI Agent Engine (reasoning engines) plus their dedicated service accounts and read-only IAM grants.

## Resources created

- **5 service accounts** — `sa-orchestrator`, `sa-sre`, `sa-devsecops`, `sa-platform`, `sa-finops`. Each is bound to its reasoning engine via `spec.service_account`, so the runtime executes under the scoped per-agent identity rather than the shared default Vertex service agent.
- **IAM bindings** — read-only observability/inventory grants per DESIGN-REVIEW §5.3, plus `roles/aiplatform.user` per agent (required for Gemini inference) and, when `agent_artifact_bucket` is set, bucket-scoped `roles/storage.objectViewer` for loading agent code. No write IAM on GCP resources.
- **5 reasoning engines** — one per agent. `agent_framework = "google-adk"`; per-agent `service_account` + `labels`; `deletion_policy` driven by `deletion_policy_prevent` (defaults `PREVENT` in prod).
- **Memory Bank** — one `google_vertex_ai_reasoning_engine` (`provider = google-beta` for the `context_spec` block) configured with generation + embedding models and a retention `ttl_config` (`memory_default_ttl`, default 30d). The beta-provider requirement is annotated inline in `main.tf`.

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
| ops_audit_topic_id | string | — | yes |
| audit_bq_dataset_id | string | audit_logs | no |
| billing_export_bq_dataset_id | string | "" | no |
| billing_export_bq_project_id | string | "" | no |
| memory_generation_model | string | gemini-2.5-flash | no |
| memory_embedding_model | string | text-embedding-005 | no |
| memory_default_ttl | string | 2592000s (30d) | no |
| agent_artifact_bucket | string | "" | no |
| labels | map(string) | {} | no |
| container_image_* | string | placeholder | no |

## Outputs

All SA emails and reasoning engine resource IDs. See `outputs.tf`.
