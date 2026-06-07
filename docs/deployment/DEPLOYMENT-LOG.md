# AOP — Terraform Deploy/Destroy Validation Log

Living record of the end-to-end **deploy → verify → destroy** validation of the
AOP platform into GCP project **`agentic-ops-platform`** (project number
`333072046868`), region **`europe-west2`**, run from branch
`chore/terraform-deploy-validation`.

- **Objective:** prove the platform deploys cleanly from Terraform and tears
  down with no residual cloud resources; make future deploys repeatable,
  auditable, cost-aware, secure, and cleanly removable.
- **Operator identity:** `eray4793@gmail.com` (gcloud ADC).
- **Terraform:** v1.14.0 · **Providers:** `hashicorp/google` + `google-beta` v7.35.0.
- **Tooling dates:** pricing/research as of 2026-06-06.

> Convention: this is an audit log. Commands and trimmed outputs are recorded
> inline. Sensitive values (billing account, tokens) are redacted or live only
> in the gitignored `sandbox.auto.tfvars`.

---

## 0. Pre-flight facts (read-only discovery)

| Check | Result |
|-------|--------|
| Project `agentic-ops-platform` | ACTIVE, number `333072046868` |
| Billing | **Enabled** (account `01xxxx-xxxxxx-xxxxxx`, redacted) |
| Organization | **None** (`gcloud organizations list` → 0) |
| APIs enabled at start | 22 (BigQuery/storage/logging/monitoring family); none of run/aiplatform/pubsub/eventarc/kms/iam/artifactregistry/secretmanager/cloudbuild |
| `orgpolicy.googleapis.com` | not enabled; org policies error (no org) |
| Key APIs (`run`, `aiplatform`, `modelarmor`, `eventarc`, `securitycenter`, …) | all **enableable** on this project+billing |
| Services have Dockerfiles | yes (`action-broker`, `slack-notifier`); `/healthz`, port 8080, `LIVE_*` default false |

**Provider feasibility:** `terraform validate` passes on `bootstrap`, `dev`,
`prod` against the real provider 7.34/7.35 schema — all resource types
(`google_vertex_ai_reasoning_engine`, `google_model_armor_floorsetting`,
`google_scc_project_*`, `google_org_policy_policy`, Eventarc) exist. The
blockers are **runtime**, not schema (see §1).

---

## 1. Findings — why the literal full deploy cannot succeed as-is

| # | Finding | Evidence | Decision |
|---|---------|----------|----------|
| F1 | `agent-runtime` deploys 6 Vertex AI **reasoning engines** (Preview API) with hard-coded `gs://REPLACE_BUCKET/<agent>/agent.pkl` pickle URIs and **no override variable**; agent code is stubs | `modules/agent-runtime/main.tf` | **Gate off** — not instantiated in the sandbox root. Document as enable-after-packaging. |
| F2 | **Org Policy** (×2) + **SCC** require an organization; this project has none | `gcloud org-policies list` → API/permission error; SCC is org-level (incl. free Standard) | Gate behind `enable_org_policies` / `enable_scc` (default false). |
| F3 | Both **Cloud Run** services omit `deletion_protection` → provider v7 default **true** blocks `terraform destroy` | `modules/{action-broker,slack-notifier}/main.tf` | Added `deletion_protection` var (default false); set false in sandbox. |
| F4 | Eventarc trigger `audit_logs_to_signals` targets a Cloud Run service **`orchestrator` that never exists** (orchestrator is a reasoning engine); second trigger targets `slack-notifier`, deployed after eventing | `modules/eventing/main.tf:287,325` | Added `enable_eventarc_triggers` (default true); set false in sandbox. |
| F5 | `foundation` VPC/AR/contacts have **no `depends_on`** on `google_project_service` → first-apply "API not used before" race | `modules/foundation/main.tf` | Added `depends_on = [google_project_service.apis]`; added `cloudbuild` to the API list. |
| F6 | `slack-notifier` Cloud Run sources secrets at `version="latest"`; **no version exists** → revision won't deploy | `modules/slack-notifier/main.tf:152-169` | Added `seed_placeholder_secret_versions` (default false); set true in sandbox (LIVE_SLACK_ENABLED=false, values unused). |
| F7 | Native **Slack** monitoring channel is verified against a live token at create → fails token-less | `modules/observability/main.tf:18` | Added `enable_slack_notification_channel` (default true); alerts route via a shared local (Pub/Sub always + Slack when enabled); set false in sandbox. |
| F8 | `dev` orders **eventing before governance**, but eventing's BQ audit *table* lives in the dataset governance creates | `environments/dev/main.tf` | Sandbox orders **governance → eventing** (possible once SCC is gated off, removing the cycle). |
| F9 | The `_AllLogs` → BigQuery sink auto-creates **non-Terraform tables** in the audit dataset → blocks dataset destroy | `modules/governance/main.tf:41` | Added `delete_contents_on_destroy` (default false); set true in sandbox. |
| F10 | Model Armor floor-setting is the newest/riskiest provider resource and screens nothing without agent traffic | `modules/governance/main.tf:70` | Added `enable_model_armor` (default true); set false in sandbox for a low-risk apply. |

All changes are **backward-compatible**: `dev` and `prod` still `validate`
clean (new variables default to prior behaviour, except the no-org-only
resources which correctly default off).

---

## 2. Module changes made (branch `chore/terraform-deploy-validation`)

- `modules/foundation`: `+cloudbuild.googleapis.com`; `depends_on` API ordering on network/AR/contacts.
- `modules/governance`: `+enable_org_policies` (false), `+enable_scc` (false), `+enable_model_armor` (true), `+delete_contents_on_destroy` (false); `count`-gated org-policy/SCC/Model-Armor; `scc_notification_pubsub_topic` now optional; outputs use `one()`.
- `modules/eventing`: `+enable_eventarc_triggers` (true); `count`-gated both triggers.
- `modules/action-broker`: `+deletion_protection` (false).
- `modules/slack-notifier`: `+deletion_protection` (false), `+seed_placeholder_secret_versions` (false) + placeholder versions, `+placeholder_secret_value`.
- `modules/observability`: `+enable_slack_notification_channel` (true); alerts route via `local.alert_notification_channels`; output uses `one()`.
- **New** `environments/sandbox/` validation root (local state) + this `docs/deployment/` set.

---

## 3. State backend strategy

The sandbox root uses **local Terraform state** deliberately, so `terraform
destroy` removes 100% of provisioned cloud resources with no residual. The
**production** path (`environments/dev|prod`) uses a **GCS backend** created by
`terraform/bootstrap` (state bucket + CMEK KMS key + WIF + runner SAs).
Bootstrap is itself a documented external prerequisite: its KMS key has
`prevent_destroy = true` and KMS keyrings/keys **cannot be deleted in GCP**
(only key versions destroyed), and the bucket is `force_destroy = false` — so
applying bootstrap leaves permanent residual. For this teardown-clean
validation we therefore **do not** apply bootstrap. See `REQUIRED-APIS.md`,
`COST-ESTIMATE.md`, and `GCLOUD-COMMANDS.md`.

---

## 4. Validate + plan

```
terraform -chdir=terraform/environments/sandbox validate   # Success
terraform -chdir=terraform/environments/sandbox plan        # Plan: 108 to add, 0 to change, 0 to destroy
```

Top resource types: 17 `google_project_service`, 14 `google_pubsub_topic`,
9 `google_service_account`, 7 `google_service_account_iam_member`,
7 `google_project_iam_member`, 5 `google_logging_metric`, 4 alert policies,
3 secrets, 3 subscriptions, 2 Cloud Run services, 1 BigQuery dataset, 1 budget.
By module: action_broker 33, foundation 24, eventing 19, observability 15,
slack_notifier 11, governance 4, root 2. No warnings.

---

## 5. Deployment execution (chronicle)

Staged apply: `-target=module.foundation` first (to create Artifact Registry +
enable APIs before building images), then build images, then the full apply.
Each row is an actual run; "fix" = the change made before the next run.

| # | Step | Result | Fix applied |
|---|------|--------|-------------|
| 1 | `apply -target=module.foundation` | 21/24 created (16 APIs, VPC, subnet, 2 FW, Artifact Registry); **3 Essential Contacts failed — 403 quota project** | Finding **F12**: added `user_project_override`+`billing_project` to providers |
| 2 | re-apply foundation | contacts now **409 CONTACT_ALREADY_EXISTS** (3 contacts share one email) | Finding **F11**: consolidate to one contact w/ all categories (+`moved`) |
| 3 | re-apply foundation | **0 add, 1 change** — contact gets SECURITY,TECHNICAL,BILLING ✅ | — |
| 4 | `gcloud builds submit` ×2 | **failed — `--mount requires BuildKit`** | added `services/cloudbuild.yaml` (DOCKER_BUILDKIT=1) |
| 5 | rebuild ×2 | both images pushed to Artifact Registry ✅ | — |
| 6 | `apply` (full) | 23 created; **budget 400 (USD≠GBP)**, **BQ sub 403 (no Pub/Sub SA BQ IAM)** | **F13**+**F16**: grant Pub/Sub SA BQ IAM; omit budget currency |
| 7 | `apply` | **budget name >60 chars**, **BQ sub 400 (AVRO↔BQ schema mismatch)** | **F13**/**F16**: gate BQ sub; shorten name |
| 8 | `apply` | 52 created (both **Cloud Run services Ready**, broker SAs, IAM…); **observability: alert 404, metric value_extractor, uptime <3 regions** | **F14**+**F17**: fix metric/uptime/filters; gate agent alerts |
| 9 | `apply` | 5 created; **SLO 400 (ALIGN_DELTA on GAUGE BOOL)** | **F15**: gate SLO |
| 10 | `apply` | **Apply complete! 0 add / 0 change / 0 destroy — 103 resources** ✅ | — |
| 11 | `plan -detailed-exitcode` | **exit 0 — "No changes. Your infrastructure matches the configuration"** ✅ | — |
| 12 | verify (gcloud) | 2 Cloud Run `Ready=True`, 14 topics, 3 secrets, 10 SAs, 1 BQ dataset, 2 images, budget present ✅ | — |
| 13 | `destroy` | 13 destroyed; **metric "still used in an alerting policy"** | **F18**: add `depends_on` alert→metric |
| 14 | `destroy` | **Destroy complete! 89 destroyed — 0 in state** ✅ | — |
| 15 | teardown verify | 0 Cloud Run / topics / secrets / AR / BQ / dashboards / contacts / SAs / VPC / FW; my budget gone ✅ | cleaned Cloud Build bucket + default VPC (§9) |

Total: **103 resources deployed**, idempotent, then **fully destroyed**.

## 6. Runtime findings + fixes (discovered during deploy)

These are in addition to the static findings F1–F10 (§1). All fixes are
committed on the branch and are backward-compatible (dev/prod still `validate`).

- **F11 — Essential Contacts: one contact per email.** The module created three
  `google_essential_contacts_contact` resources all using the same
  `essential_contacts_email`; the API keys a contact by email and 409s on the
  2nd/3rd. **Fix:** consolidated to a single contact with
  `["SECURITY","TECHNICAL","BILLING"]` + a `moved` block. (`modules/foundation`)
- **F12 — ADC quota project.** User Application Default Credentials have no
  quota project, so `essentialcontacts.googleapis.com` returned 403
  ("requires a quota project", consumer `764086051850`). **Fix (TF-native, no
  gcloud):** `user_project_override = true` + `billing_project = project_id` on
  both providers (`environments/sandbox/providers.tf`). Recommended for the
  dev/prod roots too when applying under user ADC.
- **F13 — ops.audit → BigQuery subscription.** Two problems: (a) the module
  never granted the Pub/Sub service agent BigQuery access (403 at create) —
  **fixed** by granting `roles/bigquery.dataEditor` (dataset) +
  `roles/bigquery.metadataViewer` (project) to
  `service-<num>@gcp-sa-pubsub.iam.gserviceaccount.com`; (b) with
  `use_topic_schema=true` the `ops.audit` AVRO schema and the `audit_events` BQ
  table schema **diverge** (`evidence_refs` is repeated in AVRO but `JSON` in
  BQ → 400 "Incompatible schema repeated mode"). **Gated** behind
  `enable_bq_audit_subscription` (default true; **false in sandbox**) until the
  schemas are reconciled. (`modules/eventing`)
- **F14 — Agent-Engine alert policies need a running agent.** `agent_down` and
  `decision_latency_p95` watch `aiplatform.googleapis.com/ReasoningEngine`
  *system* metrics, which don't exist until an agent emits them → 404. **Gated**
  behind `enable_agent_engine_alerts` (default true; **false in sandbox**).
  (`modules/observability`)
- **F15 — Availability SLO uses an invalid aligner.** `good_total_ratio` over
  the uptime `check_passed` (GAUGE BOOL) metric yields `ALIGN_DELTA`, rejected
  by the API. **Gated** behind `enable_slo` (default true; **false in sandbox**)
  pending a reworked SLI. (`modules/observability`)
- **F16 — Billing budget.** `currency_code="USD"` ≠ the billing account currency
  (**GBP**) → 400; and the display name exceeded the 60-char limit. **Fix:**
  omit `currency_code` (inherit account currency); shorten the name.
  (`environments/sandbox/main.tf`)
- **F17 — Observability resource bugs (fixed, not gated):**
  `aop_token_spend_total` had a `value_extractor` on an `INT64` metric (only
  valid on `DISTRIBUTION`) → changed to `DISTRIBUTION` + `bucket_options`;
  uptime checks specified one region (`["EUROPE"]`) but the API requires ≥3 →
  `["USA","EUROPE","ASIA_PACIFIC"]`; the `action_rollback_rate` and
  `detection_dwell_p95` alert filters lacked a `resource.type` restriction →
  added `cloud_run_revision` / `aiplatform...ReasoningEngine`. (`modules/observability`)
- **F18 — Destroy ordering.** Log-based metrics referenced by alert filters
  (by string) had no Terraform dependency edge, so destroy tried to delete the
  metric while its alert still used it (400). **Fix:** explicit `depends_on`
  (alert → metric), which also guarantees create ordering. (`modules/observability`)

## 7. Final state (deployed, before teardown)

103 Terraform resources. Type breakdown (selected): 17 `google_project_service`,
14 `google_pubsub_topic`, 9 `google_service_account`, 7
`google_service_account_iam_member`, 7 `google_project_iam_member`, 5
`google_logging_metric`, 4 `google_project_iam_custom_role`, 3
`google_secret_manager_secret`(+2 versions), 3 `google_pubsub_schema`, 2
`google_pubsub_subscription`, 2 `google_cloud_run_v2_service`, 2
`google_monitoring_uptime_check_config`, 2 `google_monitoring_alert_policy`, 1
each of BigQuery dataset/table, dashboard, custom service, notification
channel, log sink, VPC/subnet, Artifact Registry repo, billing budget. Both
Cloud Run services reported `Ready=True`.

## 8. Teardown

`terraform destroy` removed all 103 resources (after the F18 ordering fix). Post-
destroy verification showed **zero** of every Terraform-managed class.

## 9. Residual resources (NOT removed by `terraform destroy`)

| Residual | Why | Disposition |
|----------|-----|-------------|
| `gs://agentic-ops-platform_cloudbuild` | staging bucket auto-created by `gcloud builds submit` (non-TF) | **Removed** manually: `gcloud storage rm --recursive` (§GCLOUD-COMMANDS) |
| `default` VPC + `default-allow-*` firewall rules | auto-created by GCP when `compute.googleapis.com` was enabled (non-TF) | **Removed** manually (also closes open SSH/RDP); recreate with `gcloud compute networks create default` if ever needed |
| ~40 enabled APIs | `google_project_service.disable_on_destroy = false` (intentional — disabling APIs is risky and can break unrelated resources) | **Left enabled** (documented; harmless, no cost) |
| Google-managed service agents (`service-<num>@gcp-sa-pubsub`, `gcp-sa-aiplatform`, …) | auto-provisioned by Google on first API use; not user-deletable, not billable | **Left** (Google-managed lifecycle) |
| GCP project, billing account, pre-existing `budgetlimit` (GBP 5) budget | external prerequisites / pre-existing user resources | **Left** (explicitly out of scope per the task) |

**Net:** after teardown the project has **no Terraform-managed resources and no
deploy-created infrastructure residual** (the Cloud Build bucket and default VPC
were cleaned). Only enabled APIs + Google service agents remain, which is the
expected, documented, harmless steady state.

## 10. Outcome

✅ The AOP platform (deployable subset) **deploys end-to-end from Terraform,
reaches a stable/idempotent state, and is fully destroyable** on a standalone
no-org project. The 18 findings above were fixed (or gated with rationale) so
future deploys are repeatable, auditable, cost-aware, secure, and cleanly
removable with no hidden manual steps beyond the two documented gcloud items
(image build; residual cleanup).

---

## 11. Follow-up — un-gating, dev/prod wiring, agent research (branch `feat/aop-ungate-and-roots`)

Re-verified by a **second full deploy → destroy cycle** with the fixed items enabled.

### B — fixing the gated items
- **B1 ops.audit → BigQuery subscription — FIXED & VERIFIED.** Reconciled the
  `audit_events` BQ table to the `ops.audit` AVRO schema: `evidence_refs` →
  `STRING REPEATED`; `policy_decision`/`model`/`outcome` → `STRING` (they are
  JSON-encoded strings in AVRO). Re-deployed with `enable_bq_audit_subscription
  = true`: the subscription created and targets `audit_logs.audit_events`.
  Requires the Pub/Sub service-agent BigQuery IAM from F13.
- **Other observability — FIXED & VERIFIED.** token_spend DISTRIBUTION, uptime
  ≥3 regions, alert `resource.type` filters, and the alert→metric `depends_on`
  all created on re-deploy. Note: alerts/SLOs referencing **just-created**
  log-metric labels need a **2nd apply** (GCP metric-descriptor propagation,
  "up to 10 min" — eventual consistency, not a config error).
- **B2 SLO — SLI reworked (valid), but creation is inherently a 2nd-day op.**
  Replaced the broken `windows_based` good_total_ratio (invalid `ALIGN_DELTA` on
  the GAUGE BOOL `check_passed`) with a `request_based` good/total ratio over
  `uptime_check/check_passed{checked="true"}`. The definition is valid, but an
  SLO can only be created once the referenced metric **has time-series data** —
  a fresh, never-invoked, scale-to-zero service has none (and the broker is
  `INTERNAL_LOAD_BALANCER`, so a public uptime check can't reach it). Keep the
  improved SLI; create the SLO **after the service has metric history**, ideally
  re-based on Cloud Run request metrics. `enable_slo` default stays true; set
  **false** in the fresh sandbox deploy.
- **B3 Eventarc triggers — NOT fixed (architectural).** The
  `audit_logs→orchestrator` trigger needs a Cloud Run **orchestrator ingest
  endpoint that the architecture lacks** (orchestrator is a reasoning engine);
  the `notifications→slack-notifier` trigger must be created **after**
  slack-notifier. Both remain gated; wiring them is a 2nd-day apply once an
  orchestrator HTTP endpoint exists.

### C — dev/prod roots wired
`environments/dev` and `prod` now set the new flags explicitly:
`deletion_protection` (true prod / false dev), `enable_eventarc_triggers=false`
(no orchestrator endpoint), governance `enable_org_policies`/`enable_scc =
var.org_id != ""` (prod) or `false` (dev), `enable_model_armor` (true prod /
false dev), dev `seed_placeholder_secret_versions=true`. All three roots
`validate`. dev/prod still use the legacy `agent-runtime` (reasoning engines
need real pickles — addressed by D).

### D — agent packaging + Agent Engine (researched; CHECKPOINT before any deploy)
- `agents/deployment/deploy.py` is a **dry-run-only skeleton** (non-dry-run
  raises `NotImplementedError`); it shows the intended
  `vertexai.agent_engines.create()` call. The 5 agents are ADK 2.1 stubs with
  `build_<agent>(settings)` builders.
- **Region:** Agent Engine is region-limited and **europe-west2 is very likely
  unsupported** (as of Feb 2026 only Gemini 2.5 Flash is GA there). Deploying
  agents needs us-central1 / europe-west1 / an EU multi-region — a region change
  from the platform's europe-west2 default, or a split-region design.
- **Path:** (a) SDK — wire `deploy.py` to `agent_engines.create()` (builds +
  uploads a package, creates the reasoning engine); or (b) Terraform — pre-build
  each agent pickle to GCS and set `google_vertex_ai_reasoning_engine.
  package_pickle_gcs_uri` (the `agents/_base` module already supports this).
- **Risk/cost:** Preview API (provider drift), real Gemini token cost once
  running, stub agents (limited function). Billable + uncertain → **go/no-go
  checkpoint required before deploying.**
