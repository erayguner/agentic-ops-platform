# Governance Mapping — Agentic Operations Platform

This is the AOP-specific implementation map for the
[Agent Governance Framework](./AGENT_GOVERNANCE_FRAMEWORK.md). It is
the project's **Appendix A** — every control in the framework maps to
the file / module / Terraform resource / service account / Pub/Sub
topic / policy that implements it in this repository.

> **Conformance:** `AGENT_GOVERNANCE_FRAMEWORK v1.1`.
> **Last attested:** 2026-05-23 against §19 (minimum compliance checklist).
> **Status:** Skeleton — see `docs/DESIGN-REVIEW.md` Part 1 for the
> implementation caveats. Many controls below describe the *intent and
> surface*; the behind-the-surface logic is stubbed
> (`NotImplementedError` / `LIVE_MODE=false`) until live integrations
> land. Unchecked boxes in §19 are tracked in `docs/DESIGN-REVIEW.md`
> Part 10 (Roadmap), not silently deferred.

---

## How to use this document

For each section of the framework, this document names:

- The **primary implementation** (where the surface lives in this
  repository).
- The **status** — Implemented, Partial, Gap, Not applicable.
- A **rationale** when status is anything other than Implemented.

If you change a control's implementation, update the row in the same
PR. The cross-component Pydantic schemas in `agents/aop_common/schemas.py`
and `services/*/schemas.py` are authoritative for field names; this
document is the framework-to-code map.

---

## §3 — Agent roles and boundaries

| Sub-section | Status | Implementation |
|---|---|---|
| §3.1 role taxonomy | Implemented | Per agent in `agents/aop_<domain>/agent.py`; declared in the agent's `prompts.py`; carried in `aop_common/config.py:AopSettings.role`. |
| §3.1.1 tier crosswalk | Implemented | Five-tier numeric (0–4) is the operational scheme; see `services/action-broker/policy/action_classes.yaml`. Crosswalk to the framework's four-class taxonomy is in framework Appendix D. |
| §3.2 boundary contract | Partial | `aop_common/config.py:AopSettings` declares purpose / role / scope / approval class. Foundation-model card reference is in `aop_common/models.py:ModelFactory`. The contract is not yet a *single artefact per agent* — it is reconstructed from settings + prompts. **Gap:** consolidate into a per-agent `boundary.yaml`. |
| §3.3 multi-agent boundaries | Partial | Orchestrator (`aop_orchestrator/agent.py`) coordinates specialists via shared schemas (`aop_common/schemas.py:Finding`). A2A protocol is not yet wired; the seam is the `Finding` envelope carrying `agent_identity` and `correlation_id`. **Gap:** agent cards (framework Appendix E.1) not yet served. |

## §4 — Tool and MCP access controls

| Sub-section | Status | Implementation |
|---|---|---|
| §4.1 structured sandboxing | Implemented | All write-side execution flows through `services/action-broker/broker.py:Broker.propose_action`. Agents do not call write APIs directly. |
| §4.2 declarative policy | Implemented | `services/action-broker/policy/action_classes.yaml` — autonomy tier + bounds + required approvers per action class × environment. Loaded and schema-validated by `services/action-broker/policy.py:_load_policy`. |
| §4.3 registry-led categorisation | Implemented | Action-class catalogue enumerated and typed in `services/action-broker/executors/__init__.py`. Substring matching is not used. |
| §4.4 per-principal budgets | Gap | Currently policy is per-action-class per-env. Per-agent rate limits are an open roadmap item (`docs/DESIGN-REVIEW.md` Part 10). |
| §4.5 MCP server posture | Implemented | Google-managed MCP fleet (BigQuery, Cloud Logging, Monitoring, Asset Inventory, Workflows, SCC, etc.) wired through `aop_common/mcp_tools.py:McpToolset`. Custom MCP server for the Action Broker exposed by `services/action-broker/main.py`; runs as Cloud Run with IAM-bound identity. |

## §5 — Approval gates

| Sub-section | Status | Implementation |
|---|---|---|
| §5.1 when approval is required | Implemented | Driven by autonomy tier in `services/action-broker/policy/action_classes.yaml`. Tier ≥ 3 requires per-action approval. |
| §5.2 approval primitive | Implemented | Slack-button approval via `services/slack-notifier/interactivity.py` → publishes `ActionApproval v1` to `ops.actions.approved`. Push-subscription wiring lives in `terraform/modules/action-broker/`. |
| §5.3 approver pools and quorum | Implemented | Implemented at policy level (`policy/action_classes.yaml.required_approvers`). 2-of-N quorum supported for irreversible classes. Pool review is part of the 2-reviewer PR gate (`CONTRIBUTING.md`). |
| §5.4 time-boxing | Implemented | `APPROVAL_WINDOW_MINUTES` (default 15 min) on the Action Broker; carried as `approval_window_until` in `ActionRequest v1`. |
| §5.5 override and revocation | Partial | Slack `Reject` is wired; revocation-before-consumption is stubbed in `services/action-broker/broker.py`. |

## §6 — Policy enforcement

| Sub-section | Status | Implementation |
|---|---|---|
| §6.1 policy as code | Implemented | `services/action-broker/policy/action_classes.yaml` (broker autonomy policy), `terraform/modules/governance/*.tf` (org-level GCP policy). |
| §6.2 per-event evaluation | Implemented | `services/action-broker/policy.py:PolicyEngine.decide` evaluates each `ActionRequest` independently. |
| §6.3 fail-closed defaults | Implemented | `PolicyEngine.decide` rejects unknown action classes and requests without an idempotency key. |
| §6.4 no silent bypass | Implemented | `LIVE_MODE=false` and `LIVE_SLACK_ENABLED=false` log loudly. Bypass is environment-level (set at deploy time), never per-request, and never settable by the agent. |

## §7 — Least-privilege execution

| Sub-section | Status | Implementation |
|---|---|---|
| §7.1 identity | Implemented | Each agent has a dedicated service account (`terraform/modules/agent-runtime/main.tf`): `sa-orchestrator`, `sa-sre`, `sa-devsecops`, `sa-platform`, `sa-finops`. WIF for CI (`sa-tf-runner-<env>`) with **per-environment principalSet binding** — dev runner is bound to `attribute.repository`, prod runner to `attribute.environment/deploy-prod` so prod impersonation requires a workflow run that opts into a GitHub Environment with manual reviewer gating. The WIF provider's `attribute_condition` additionally fences by `assertion.repository`, `assertion.ref`, and `assertion.event_name`. No exported keys. |
| §7.2 permissions | Implemented | Read-side agents hold no write IAM. Per-action-class SAs (`sa-action-<class-slug>`) hold the narrow grant needed; bound by Principal Access Boundary. **Three custom roles** narrower than the closest predefined role are used where the predefined role bundles excessive permissions: `aopIamServiceAccountKeyDisableOnly` (only `iam.serviceAccountKeys.disable/get/list` — no create, no delete), `aopSecretVersionDisableOnly` (only `secretmanager.versions.disable/get/list` + read on secrets — no create/delete/setIamPolicy), `aopSccFindingMuteOnly` (only `securitycenter.findings.setMute/get/list` — no update, no setState). See `terraform/modules/action-broker/main.tf` `google_project_iam_custom_role.*`. The `sa-tf-runner-<env>` SAs hold `roles/storage.objectAdmin` (NOT `storage.admin`) on the matching state bucket — exactly what GCS-backend native locking needs, no bucket-level admin. |
| §7.3 tool scope | Implemented | `aop_common/mcp_tools.py:McpToolset` allow-lists Google-managed MCP servers per agent. The allow-list is tighter than the IAM-granted surface. The Action Broker (single write surface) is reachable from agent SAs via an explicit `roles/run.invoker` allow-list composed at the env root (`terraform/environments/<env>/main.tf` `google_cloud_run_v2_service_iam_member.agent_invoke_broker`); no other principal can call the broker (ingress = `INTERNAL_LOAD_BALANCER`, authentication required). |
| §7.4 data scope | Implemented | Project-scoped queries from `aop_common/policy_client.py:OrgContextClient`; no `SELECT *` in the skeleton. FinOps' BigQuery grant is **dataset-scoped** (only the billing export dataset) when `billing_export_bq_dataset_id` is set in tfvars; falls back to project-wide `bigquery.dataViewer` when unset (looser; documented). |
| §7.5 network scope | Implemented | VPC Service Controls via `terraform/modules/governance/`; egress denied by default. Code execution uses Vertex AI Agent Engine Code Execution. |
| §7.6 managed agent runtime | Implemented | Vertex AI Agent Engine (`terraform/modules/agent-runtime/google_vertex_ai_reasoning_engine`); inherits OTel tracing, Cloud Monitoring, Cloud Logging, Agent Identity, Threat Detection. |

## §8 — Auditability

| Sub-section | Status | Implementation |
|---|---|---|
| §8.1 what is recorded | Implemented | All `AuditRecord v1` events to `ops.audit` Pub/Sub topic; schema in `agents/aop_common/schemas.py`. |
| §8.2 tamper evidence | Partial | BigQuery `audit.events` is append-only via IAM denying `bigquery.tables.delete` to agent SAs. **Gap:** hash chaining + daily signed manifest are not yet wired; currently relies on BigQuery + Cloud Logging immutability. Roadmap. |
| §8.3 correlation | Implemented | Every schema in `aop_common/schemas.py` carries `correlation_id`; orchestrator preserves it across hops. |
| §8.4 retention | Implemented | Cloud Logging sinks + BigQuery dataset retention encoded in `terraform/modules/governance/`. 365d minimum; 7y for regulated data. |
| §8.5 independent storage | Partial | Audit BigQuery dataset lives in the prod project but its IAM denies agent identities `Delete*` / `bigquery.tables.delete`. **Gap:** org-level log sink to a separate logs project is not yet wired. |

## §9 — Observability

| Sub-section | Status | Implementation |
|---|---|---|
| §9.1 three surfaces | Implemented | Traces via OpenTelemetry (`opentelemetry-exporter-gcp-trace` in `agents/pyproject.toml`); metrics via Cloud Monitoring (`terraform/modules/observability/`); logs structured JSON via `google-cloud-logging`. |
| §9.2 anomaly and drift detection | Partial | Cloud Monitoring alert policies in `terraform/modules/observability/`. **Gap:** z-score / χ² baselines per agent are roadmap items. |
| §9.3 replay | Gap | `Finding` events on `ops.findings` can be replayed manually; full transcript replay is not yet wired. Roadmap. |
| §9.4 health probes | Implemented | Cloud Run health checks on `services/action-broker/main.py` and `services/slack-notifier/main.py`; Pub/Sub DLQ monitors in `terraform/modules/observability/`. |

## §10 — Explainability

| Sub-section | Status | Implementation |
|---|---|---|
| §10.1 required rationale | Implemented | Every `Finding v1` carries `summary` and `cause_hypothesis`; every `Recommendation v1` carries `rationale` (`aop_common/schemas.py`). Pydantic-validated. |
| §10.2 decision records | Implemented | `services/action-broker/policy.py:Decision` records verdict + reason; emitted to `ops.actions.requested` + `ops.audit`. |
| §10.3 post-action reports | Partial | Slack notifications via `services/slack-notifier/blockkit.py` render rationale + outcome. **Gap:** session-close reports are not yet generated. |
| §10.4 no unexplained actions | Implemented | `Recommendation v1.rationale` is a required Pydantic field; producing an action without one is a schema error. |
| §10.5 fairness and bias | Not applicable | AOP agents allocate findings (about cost, drift, posture), not opportunities across people, teams, or customers. No protected-attribute exposure. |

## §11 — Data handling

| Sub-section | Status | Implementation |
|---|---|---|
| §11.1 data classification | Implemented | Per-agent in the boundary contract; AOP handles internal + confidential only (no PII / PHI / PCI). |
| §11.2 input filters | Implemented | `services/slack-notifier/redaction.py` redacts PII before posting; pre-commit `gitleaks` blocks committed secrets. |
| §11.3 output filters | Implemented | Same `redaction.py` stack on the outbound path. |
| §11.4 provider guardrails | Implemented | Model Armor floor settings via `terraform/modules/governance/` (`google_model_armor_floor_setting` + per-template settings in `INSPECT_AND_BLOCK` mode). |
| §11.5 minimisation | Implemented | `aop_common/audit.py:AuditEmitter` truncates payload previews; raw payloads stay in Cloud Logging with appropriate retention. |
| §11.6 conversational memory | Gap | Vertex AI Agent Engine Memory Bank (Preview) is not yet wired. Seam noted in `agents/aop_orchestrator/agent.py`. |
| §11.7 data lineage | Gap | Dataplex Data Lineage is documented in `docs/DESIGN-REVIEW.md` Part 8 but not wired in the scaffold. |
| §11.8 DLP and DP | Partial | Sensitive Data Protection wired at the org level via `terraform/modules/governance/`. **FinOps BigQuery surface** is dataset-scoped via `billing_export_bq_dataset_id` (prod) — only the billing export dataset is readable, not every BigQuery dataset in the project. Differential privacy is not applicable — AOP does not serve cohort analytics. |

## §12 — Security

| Sub-section | Status | Implementation |
|---|---|---|
| §12.1 threat model | Implemented | Documented in `docs/DESIGN-REVIEW.md` Part 8.1. |
| §12.2 secret hygiene | Implemented | Secrets in Secret Manager; `auth_token_wo` write-only attribute on the Slack notification channel; pre-commit `gitleaks`. |
| §12.3 supply chain | Partial | Provider pin `~> 7.33` (`terraform/versions.tf`); container builds via `services/*/Dockerfile` use uv `--frozen`. **Gap:** SLSA provenance and Sigstore signing are roadmap items. |
| §12.4 signed artifacts | Partial | `auth_token_wo` for the Slack token; signed audit exports are roadmap. |
| §12.5 boundary hardening | Implemented | VPC Service Controls + egress denylist in `terraform/modules/governance/`. |
| §12.6 managed threat detection | Partial | Security Command Center v2 (`google_scc_v2_source` in `terraform/modules/governance/`); SCC findings flow through `ops.signals`. Agent Engine Threat Detection (Preview) feeds the same sink. **Gap:** alerting on agent-specific patterns is not yet tuned. |
| §12.7 red-teaming | Gap | Cadence stated in `docs/DESIGN-REVIEW.md` Part 8.7; operationalisation is the deployer's responsibility today. |

## §13 — Resilience

| Sub-section | Status | Implementation |
|---|---|---|
| §13.1 circuit breakers | Partial | Cloud Run native concurrency + retry; per-MCP-server breakers are roadmap. |
| §13.2 dead-letter queues | Implemented | All `ops.*` topics have a `.dlq` counterpart (`terraform/modules/eventing/main.tf`). |
| §13.3 reconciliation | Partial | Cloud Monitoring uptime checks + Pub/Sub backlog alerts (`terraform/modules/observability/`). Full reconciliation agent is roadmap. |
| §13.4 degraded modes | Implemented | `LIVE_MODE=false` and `LIVE_SLACK_ENABLED=false` defaults are the canonical degraded mode for the skeleton. Fail-closed for missing approval gateway. |
| §13.5 replay and idempotency | Implemented | `services/action-broker/idempotency.py` uses Firestore for idempotency keys; every `ActionRequest` carries `idempotency_key`. |

## §14 — Human oversight

| Sub-section | Status | Implementation |
|---|---|---|
| §14.1 kill-switch | Partial | Slack `Reject` button on a pending action halts the action chain via `ops.actions.approved` carrying `decision: rejected`. **Gap:** session-level halt (denying all in-flight tool calls for a session) is not yet wired. |
| §14.2 override API | Implemented | Slack interactivity (`services/slack-notifier/interactivity.py`) — approve / reject. |
| §14.3 interactive review | Implemented | Block Kit message includes summary, affected component, impact, likely cause, recommended actions, approval flag, links (`services/slack-notifier/blockkit.py`). |
| §14.4 transparency | Implemented | Channel routing by domain + severity in `services/slack-notifier/blockkit.py:resolve_channel`; alerts carry full context (who / what / impact / next / escalation). |

## §15 — Incident response

| Sub-section | Status | Implementation |
|---|---|---|
| §15.1 definition | Implemented | Documented in `docs/DESIGN-REVIEW.md` Part 8.3. |
| §15.2 runbook structure | Partial | Per-action-class runbooks live in `services/action-broker/executors/*.py` docstrings. **Gap:** per-incident-class runbooks are roadmap. |
| §15.3 forensic guarantees | Partial | BigQuery `audit.events` immutability + Cloud Logging immutability. **Gap:** signed export procedure is roadmap. |
| §15.4 blameless culture | Implemented | Reflected in the 2-reviewer PR policy for prod-touching changes (`CONTRIBUTING.md`). |

## §16 — Change management

| Sub-section | Status | Implementation |
|---|---|---|
| §16.1 version control for everything | Implemented | All policies (`policy/action_classes.yaml`), prompts (`aop_*/prompts.py`), tool catalogues (`aop_common/mcp_tools.py`), approver pools (`policy/action_classes.yaml`), boundary settings (`aop_common/config.py`), and model IDs in git. |
| §16.2 review requirements | Implemented | `CONTRIBUTING.md` Pull-request process — 2 reviewers for `terraform/environments/prod/`, `services/action-broker/policy/action_classes.yaml`, any `schemas.py` change, security-labelled PRs. |
| §16.3 pre-flight gates | Partial | Pre-commit hooks (`gitleaks`, `ruff`, `terraform fmt+validate+tflint+trivy`, `conventional-pre-commit`) + `pytest`. **Gap:** regression eval harness is roadmap. |
| §16.4 rollout | Implemented | Dev → prod via separate Terraform roots (`terraform/environments/{dev,prod}/`); canary on Cloud Run revisions. |
| §16.5 deprecation | Implemented | Conventional Commits `BREAKING CHANGE:` footer (`CONTRIBUTING.md`); one-release deprecation window. |
| §16.6 fine-tuning | Not applicable | AOP uses foundation Gemini models exclusively; no fine-tuning or adapter governance. |

## §17 — Operating model

| Sub-section | Status | Implementation |
|---|---|---|
| §17.1 roles | Partial | Agent owner / platform team / security / compliance / SRE assignments are the deployer's responsibility; the repo names *framework-level* owners (this document, `CONTRIBUTING.md`, `SECURITY.md`). Framework owner role is upstream (per the framework's §20.2). |
| §17.2 review cadence | Documented | Cadence stated; operationalisation is the deployer's responsibility. |
| §17.3 evidence pack | Partial | BigQuery `audit.events` + the §19 attestation in this document. **Gap:** signed-export bundling tool is roadmap. |

## §18 — Maturity levels

AOP currently sits at **L1 (Foundational)** in the framework's
maturity scale. The path to **L2 (Production-ready)** is gated by the
gaps named in §19 below and tracked in `docs/DESIGN-REVIEW.md` Part 10.

---

## §19 — Minimum compliance checklist (project attestation)

This is the AOP attestation against the framework's §19 minimum
compliance checklist. Each box is one of:

- `[x]` — implemented in this repository.
- `[~]` — partial; a credible surface exists, but completion is a
  roadmap item.
- `[ ]` — gap; explicitly tracked.
- `n/a` — not applicable to the AOP scope, with a one-line reason.

### Identity and access

- [x] Agent runs under WIF / managed identity — no static keys.
      WIF pool / GitHub provider in `terraform/bootstrap/main.tf`. **Prod
      runner SA is impersonatable ONLY from runs declaring the
      `deploy-prod` GitHub Actions environment** (manual-reviewer gated);
      dev runner is impersonatable from any push to main or PR run.
      `attribute_condition` additionally fences by `assertion.ref` and
      `assertion.event_name`.
- [x] IAM permissions ⊆ boundary contract.
      (`terraform/modules/agent-runtime/`, per-SA grants scoped by PAB;
      three **custom roles** (`aopIamServiceAccountKeyDisableOnly`,
      `aopSecretVersionDisableOnly`, `aopSccFindingMuteOnly`) used where
      the closest predefined role bundles excessive permissions.)
- [x] Tool allow-list ⊆ IAM permissions.
      (`aop_common/mcp_tools.py`; action broker reachable from agent SAs
      via an explicit `run.invoker` allow-list, not project-wide.)

### Governor

- [x] Single enforcement point for all tool calls.
      (`services/action-broker/broker.py:propose_action`)
- [x] `default_allow = False` in production.
      (`services/action-broker/policy.py:PolicyEngine`)
- [x] Policy schema-validated at load.
      (`services/action-broker/policy.py:_load_policy`)
- [ ] Per-principal budgets, not global. **Gap** — Roadmap.

### Provider controls

- [x] Model Armor template + floor settings in `INSPECT_AND_BLOCK`.
      (`terraform/modules/governance/google_model_armor_*`)
- [x] Gemini `safety_settings` per HarmCategory.
      (`aop_common/models.py:ModelFactory`)
- [x] Model invocation logging / Data-Access logs enabled.
      (`terraform/modules/governance/`)
- [x] Per-agent identity in use (dedicated SA per agent; SPIFFE
      placeholder accepted for forward-compat).
- [~] Managed agent threat detection wired. SCC v2 source live;
      Agent Engine Threat Detection (Preview) sink in place; alerting
      on agent-specific patterns is **roadmap**.

### Evaluation

- [ ] Regression eval harness covers tool trajectory / response
      match / response quality / tool-use quality / groundedness /
      safety. **Gap** — Roadmap.
- [ ] Model pin upgrades run the full suite. **Gap** — Roadmap.
- [ ] Eval results are a merge gate. **Gap** — Roadmap.

### Memory and sessions

- [ ] Retention policy declared per memory store. **Gap** — Memory
      Bank is Preview and not yet wired.
- [ ] User-scoped deletion procedure tested. **Gap**.
- [ ] Cross-tenant retrieval denied by construction. **Gap**.
- [ ] Retrieved memory passes through input filters. **Gap**.

### Data lineage and DLP

- [ ] Every retrieval source versioned; version recorded on
      consuming `AgentStep`. **Gap** — Roadmap.
- [x] Prompt templates stored in git; edits are PRs.
      (`agents/aop_*/prompts.py`)
- [ ] Data Catalog / Dataplex lineage queryable by corpus owner.
      **Gap** — Roadmap.
- [x] Sensitive Data Protection enabled at org level.
      (`terraform/modules/governance/`)

### Supply chain

- [ ] SLSA ≥ Level 2. **Gap** — Roadmap.
- [ ] Container images signed (Sigstore / cosign / provider-native).
      **Gap** — Roadmap.
- [x] MCP server binaries pinned. (Google-managed MCP fleet; no
      third-party MCP servers in the scaffold.)

### Third-party tool access

- [x] No shared long-lived tokens.
- [x] Logs show both user and agent identity on delegated calls.

### Fairness (allocative agents only)

- n/a — AOP allocates findings, not opportunities. No protected-
  attribute exposure.

### Red-teaming

- [ ] Quarterly red-team for Operator. **Gap** — operationalised by
      deployer.
- [ ] Coverage spans direct + indirect prompt injection / tool-chain
      escalation / exfiltration / sandbox escape. **Gap**.
- [ ] Novel findings produce regression cases. **Gap**.

### Code execution

- [x] Named provider-managed sandbox.
      (Vertex AI Agent Engine Code Execution via
      `terraform/modules/agent-runtime/`)

### Model documentation

- [x] Foundation model card referenced in boundary contract.
      (`aop_common/config.py:AopSettings.model_id`, default
      `gemini-3-pro`)
- n/a — no tuned models.

### Fine-tuning

- n/a — AOP uses foundation Gemini models exclusively.

### Approvals

- [x] Out-of-band approval gateway wired.
      (`services/slack-notifier/interactivity.py`)
- [x] Destructive actions use deferred executor (RoC equivalent).
      (`services/action-broker/broker.py:propose_action` Tier ≥ 3
      path)
- [x] Approver pool ≥ 2 for irreversibles.
      (`services/action-broker/policy/action_classes.yaml`)
- [x] Approvals expire.
      (`APPROVAL_WINDOW_MINUTES`, default 15 min)

### Audit

- [ ] Chained checksum; chain-break load-time error. **Gap** —
      currently relies on BigQuery + Cloud Logging immutability.
- [ ] Daily signed manifest. **Gap** — Roadmap.
- [ ] `export_signed` available. **Gap** — Roadmap.
- [~] Independent storage, different blast radius. Audit BigQuery
      dataset IAM denies agent SAs; org-level log sink to a separate
      logs project is roadmap.

### Observability

- [x] Per-session `AgentTrace` persisted.
      (OpenTelemetry + Cloud Trace via `agents/pyproject.toml`)
- [x] Rationale populated for every step.
      (`Finding v1.cause_hypothesis`, `Recommendation v1.rationale`
      — required Pydantic fields)
- [~] Call-rate + tool-distribution + token anomaly detectors live.
      Cloud Monitoring alerts in place; z-score / χ² baselines are
      roadmap.
- [ ] Replay tool available. **Gap** — Roadmap.

### Content filters

- [x] PII redactor on input and output.
      (`services/slack-notifier/redaction.py`)
- [x] Secret scanner blocks on match.
      (Pre-commit `gitleaks`; runtime sweep in `redaction.py`)
- [x] Prompt-injection heuristic alongside provider filter.
      (Model Armor `INSPECT_AND_BLOCK` is the primary; lightweight
      heuristic in `aop_common/policy_client.py:OrgContextClient`)

### Human oversight

- [~] Kill-switch halts a session in < 1 minute. Slack `Reject`
      halts the action chain; full session-level halt is roadmap.
- [x] Override API emits audit event.
      (`services/slack-notifier/interactivity.py` → `ops.audit`)
- [x] Alerts are contextualised (who / what / why / next /
      escalation). (`services/slack-notifier/blockkit.py`)

### Change management

- [x] Policies, prompts, approver pools all in git.
- [x] Pre-flight CI gates (policy schema, lint, format, secret scan,
      terraform validate / tflint / trivy, conventional commits).
      (`.pre-commit-config.yaml`)
- [~] Staged rollout with canary burn-in. Cloud Run traffic split is
      available; canary windows are not yet codified in the rollout
      pipeline.
- [x] Deprecation window on breaking defaults.
      (Conventional Commits; see `CONTRIBUTING.md`)

### Incident response

- [~] Runbook per incident class. Per-action-class runbooks exist
      (`services/action-broker/executors/*.py`); per-incident-class
      runbooks are roadmap.
- [ ] Forensic export procedure documented. **Gap** — Roadmap.
- [ ] Quarterly DR / kill-switch exercise. **Gap** — operationalised
      by deployer.

---

## Least-privilege tightenings applied (2026-05-23)

The following IAM surface tightenings were applied without changing the
shape of the action-class catalogue, schemas, or autonomy tier matrix.
All three Terraform roots (`bootstrap`, `environments/dev`,
`environments/prod`) still pass `terraform validate`.

| Surface | Before | After |
|---|---|---|
| WIF provider attribute mapping | repository + actor + subject | + `ref`, `environment`, `event_name` |
| WIF attribute condition | repository only | repository AND (`refs/heads/main` OR `pull_request` OR `environment` declared) |
| WIF prod runner binding | repo-wide principalSet | `attribute.environment/deploy-prod` only (requires GitHub Actions manual approval gate) |
| `sa-tf-runner-<env>` on state bucket | `roles/storage.admin` | `roles/storage.objectAdmin` (no bucket delete, no IAM mutation) |
| `sa-action-iam-disable-key` | `roles/iam.serviceAccountKeyAdmin` (includes `create` + `delete`) | Custom role `aopIamServiceAccountKeyDisableOnly` (only `disable/get/list`) |
| `sa-action-secret-disable` | `roles/secretmanager.admin` (includes `create/delete/setIamPolicy`) | Custom role `aopSecretVersionDisableOnly` (only `versions.disable/get/list` + `secrets.get/list`) |
| `sa-action-scc-mute` | `roles/securitycenter.findingsEditor` (includes `update/setState`) | Custom role `aopSccFindingMuteOnly` (only `findings.setMute/get/list`) |
| `sa-action-workflows-run` | project-wide `roles/workflows.invoker` | Same role, optional IAM condition (`var.workflows_invoker_resource_pattern`) restricts to a workflow-name prefix |
| FinOps BigQuery | project-wide `roles/bigquery.dataViewer` | Dataset-scoped on the billing export dataset (when `billing_export_bq_dataset_id` is set); `roles/bigquery.jobUser` at project level for query execution |
| Action-broker invoker grants | only the broker SA (self-invoke) | self-invoke + explicit per-agent-SA `run.invoker` allow-list composed at env-root |
| Specialist agent Pub/Sub publish (findings / notifications / audit) | missing (functional gap) | `for_each` bindings on each specialist SA × topic at narrow per-topic scope |
| Orchestrator + all-agent Pub/Sub publish on `ops.audit` | missing (functional gap) | `for_each` binding across `local.all_agent_sa_emails` |

Validated with `terraform validate` on bootstrap + dev + prod roots, and `terraform fmt -recursive` clean.

---

## Open gaps summary

The AOP skeleton is **L1 (Foundational)**. The gaps that block L2
graduation are, in priority order:

1. **Per-principal budgets** (§4.4 / §19 Governor).
2. **Regression eval harness** (§16.3 / §19 Evaluation).
3. **Hash-chained audit + signed exports** (§8.2 / §19 Audit).
4. **Anomaly detectors (z-score / χ²)** (§9.2 / §19 Observability).
5. **Session-level kill-switch** (§14.1 / §19 Human oversight).
6. **Memory Bank wiring** (§11.6 / §19 Memory).
7. **Data lineage** (§11.7 / §19 Data lineage).
8. **SLSA Level 2 + image signing** (§12.3 / §19 Supply chain).
9. **Per-incident-class runbooks + forensic export** (§15.2).
10. **Replay tool** (§9.3 / §19 Observability).
11. **Agent cards + A2A wiring** (framework §3.3 / Appendix E).

All eleven are tracked in `docs/DESIGN-REVIEW.md` Part 10 (Roadmap).

---

## Maintenance

Update this mapping in the same PR as any change that:

- Adds or removes an implementation surface for a framework control.
- Moves a status (Gap → Partial → Implemented or back).
- Adopts a new framework version (also update the `Conformance:` line
  above and re-run the §19 attestation).

The 2-reviewer rule in `CONTRIBUTING.md` applies to any change to
this file because it is a project-level governance artefact.
