# Required Google Cloud APIs

Every API the AOP platform needs, **where it is enabled in Terraform**, and what
it is for. Enablement is managed by `google_project_service` resources — no API
is enabled by a manual `gcloud services enable` in the normal flow.

## Enabled by Terraform

### `terraform/bootstrap` (production state backend; not applied in the validation)

Enabled with `disable_on_destroy = false`.

| API                             | Purpose                                    |
| ------------------------------- | ------------------------------------------ |
| `cloudkms.googleapis.com`       | CMEK key for the GCS state bucket          |
| `iam.googleapis.com`            | WIF pool/provider, runner service accounts |
| `iamcredentials.googleapis.com` | Workload Identity Federation token minting |
| `storage.googleapis.com`        | GCS Terraform state buckets                |

### `terraform/modules/foundation` (`local.required_apis`, applied to every env)

Enabled with `disable_on_destroy = false`, `disable_dependent_services = false`.
Resource ordering fixed so dependent resources wait for enablement (finding F5).

| API                                   | Purpose                         | Consumed by                                            |
| ------------------------------------- | ------------------------------- | ------------------------------------------------------ |
| `serviceusage.googleapis.com` \*      | enable/disable other APIs       | the `google_project_service` resources themselves      |
| `cloudresourcemanager.googleapis.com` | project metadata, IAM bindings  | all project IAM, `data.google_project`                 |
| `compute.googleapis.com`              | VPC, subnet, firewall           | foundation networking                                  |
| `artifactregistry.googleapis.com`     | container image repo            | foundation AR repo; Cloud Run images                   |
| `essentialcontacts.googleapis.com`    | Essential Contacts              | foundation contact                                     |
| `iam.googleapis.com`                  | service accounts, custom roles  | all SAs / IAM                                          |
| `pubsub.googleapis.com`               | topics, schemas, subscriptions  | eventing                                               |
| `run.googleapis.com`                  | Cloud Run v2 services           | action-broker, slack-notifier                          |
| `secretmanager.googleapis.com`        | secrets + versions              | slack-notifier, action-broker                          |
| `aiplatform.googleapis.com`           | Vertex AI / Agent Engine        | agent-runtime (gated), agent IAM, Agent-Engine metrics |
| `eventarc.googleapis.com`             | Eventarc triggers               | eventing (gated)                                       |
| `bigquery.googleapis.com`             | audit dataset/table             | governance, eventing                                   |
| `logging.googleapis.com`              | log sink, log-based metrics     | governance, observability                              |
| `monitoring.googleapis.com`           | dashboards, alerts, uptime, SLO | observability                                          |
| `securitycenter.googleapis.com`       | SCC (gated; org-only)           | governance (gated off)                                 |
| `modelarmor.googleapis.com`           | Model Armor (gated)             | governance (gated off)                                 |
| `cloudbuild.googleapis.com`           | build container images          | image build step (added: finding F5)                   |

\* `serviceusage` must be enabled before Terraform can manage any service; it is
enabled by default on new projects. If a project ever has it disabled, enable it
once with `gcloud services enable serviceusage.googleapis.com` (the single
unavoidable bootstrap API).

### `terraform/environments/sandbox` (root)

| API                             | Purpose                            |
| ------------------------------- | ---------------------------------- |
| `billingbudgets.googleapis.com` | the Cloud Billing budget guardrail |

## Needed only for the agent tier (currently gated off)

When the Vertex AI reasoning engines / agent IAM are enabled, add these (the
bound agent roles need them to function at runtime; add to `foundation`
`required_apis` when un-gating agents):

| API                                                               | For                                    |
| ----------------------------------------------------------------- | -------------------------------------- |
| `cloudscheduler.googleapis.com`                                   | per-agent Cloud Scheduler triggers     |
| `recommender.googleapis.com`                                      | FinOps agent recommendations           |
| `cloudtrace.googleapis.com`, `clouderrorreporting.googleapis.com` | SRE agent roles                        |
| `cloudasset.googleapis.com`                                       | DevSecOps / Platform agent roles       |
| `clouddeploy.googleapis.com`                                      | Platform agent role                    |
| `datastore.googleapis.com` (Firestore)                            | orchestrator `datastore.user`          |
| `orgpolicy.googleapis.com`                                        | Org Policy (only with an organization) |

## Notes

- **Deployed-subset API set:** the 16 foundation APIs + `billingbudgets` =
  the full set required for the validated deploy. Confirmed all enableable on
  `agentic-ops-platform` (billing enabled).
- **`securitycenter` / `modelarmor`** are enabled by foundation but their
  _resources_ are gated off here (org-only / no agent traffic). Enabling an
  unused API has no cost.
- **On destroy:** APIs are **not** disabled (`disable_on_destroy = false`). This
  is intentional (disabling APIs can break unrelated resources and is rarely
  desirable). To fully reset, disable manually with `gcloud services disable`.
