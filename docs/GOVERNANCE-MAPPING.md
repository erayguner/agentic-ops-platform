# Governance Mapping — Agentic Operations Platform

This is the AOP-specific implementation map for the
[Agent Governance Framework](./AGENT_GOVERNANCE_FRAMEWORK.md). It is
the project's **Appendix A** — every control in the framework maps to
the file / module / Terraform resource / service account / Pub/Sub
topic / policy that implements it in this repository.

> **Conformance:** `AGENT_GOVERNANCE_FRAMEWORK v1.1`.
> **External-standard crosswalk:** OWASP Top 10 for Agentic Applications
> (ASI01–ASI10) and OWASP Non-Human Identity Top 10 (2025), per the OWASP
> *State of Agentic AI Security and Governance* v2.01 (June 2026). See the
> [ASI / NHI crosswalk](#owasp-top-10-for-agentic-applications-asi01asi10-crosswalk)
> below.
> **Zero Trust crosswalk:** Anthropic *Zero Trust for AI Agents* (2026) — see the
> [capability-tier crosswalk](#zero-trust-for-ai-agents-crosswalk-anthropic-2026)
> below and the defensive-operations runbook
> [`DEFENSIVE-OPERATIONS.md`](./DEFENSIVE-OPERATIONS.md).
> **Last attested:** 2026-06-04 against §19 (minimum compliance checklist).
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

## OWASP Top 10 for Agentic Applications (ASI01–ASI10) crosswalk

The internal `AGENT_GOVERNANCE_FRAMEWORK` already cross-references NIST AI RMF,
the EU AI Act, ISO/IEC 42001, SOC 2, SAIF, and NCSC (framework §2.1). This
section adds the crosswalk to the **OWASP Top 10 for Agentic Applications**
(ASI01–ASI10, Dec 2025), the anchor taxonomy of the OWASP *State of Agentic AI
Security and Governance* v2.01. Each row names the implementing surface, a
status, and any gap this report surfaces.

Status key: `Implemented` · `Partial` (credible surface, completion tracked) ·
`Gap` (tracked, not silently deferred).

| ASI | Threat | Status | Implementation & gaps |
|---|---|---|---|
| **ASI01** | Agent Goal Hijack (direct/indirect prompt injection) | Partial | Model Armor floor settings in `INSPECT_AND_BLOCK` (`terraform/modules/governance/`); Gemini `safety_settings` per HarmCategory (`aop_common/models.py`); prompt-injection heuristic (`aop_common/policy_client.py:OrgContextClient`); PII/secret redaction (`services/slack-notifier/redaction.py`). Structural mitigation: a hijacked agent cannot write directly — every mutation goes through the Action Broker chokepoint under policy + approval. **Gap:** plan-divergence detection (action sequence vs declared intent). |
| **ASI02** | Tool Misuse & Exploitation | Implemented (write side) | Single enforcement point (`services/action-broker/broker.py:propose_action`); declarative typed-rule policy (`policy/action_classes.yaml` → `policy.py:PolicyEngine`, fail-closed); registry-led action classes, no substring matching (`executors/__init__.py`); bounds validation (`policy.py:_check_bounds`); tool allow-list ⊆ IAM (`aop_common/mcp_tools.py`). **Gap:** per-principal call/rate budgets (§4.4). |
| **ASI03** | Identity & Privilege Abuse | Partial | Per-agent service accounts, WIF (no static keys), three custom roles narrower than the closest predefined role, Principal Access Boundary, dataset-scoped FinOps BigQuery, per-agent `run.invoker` allow-list (`terraform/modules/agent-runtime/`, `terraform/modules/action-broker/`). Each reasoning engine now runs under its **dedicated per-agent SA** (`spec.service_account`) rather than the shared default Vertex service agent, so the scoped grants actually bind to the runtime identity. Static-NHI hygiene is strong (see NHI crosswalk). **Gap (v2.01 "Agent Identity"):** Google-managed `AGENT_IDENTITY` (provider-supported now, but re-points every SA-scoped binding), runtime identity *attestation*, JIT privilege, identity chaining (RFC 8693 token exchange / confused-deputy binding), and an Agent Naming Service are not yet wired. |
| **ASI04** | Agentic Supply Chain Vulnerabilities | Partial → strengthened | Build-time SBOM in CycloneDX **and** SPDX with Sigstore-signed SLSA provenance (`.github/workflows/sbom.yml`); curated AI Bill of Materials inventorying models, agents, MCP servers and tool connectors (`docs/aibom.yaml`); Trivy fs+config scans (`.github/workflows/trivy.yml`); dependency + licence review (`dependency-review.yml`); managed Google MCP fleet only (no third-party MCP servers); `uv --frozen` builds; pinned provider versions and SHA-pinned Actions. **Gap:** SLSA Level 3, container-image signing + admission control (no image build/push pipeline in this repo yet), and MCP tool-catalogue drift detection at session start (framework §4.5). |
| **ASI05** | Unexpected Code Execution (RCE) | Implemented | Code execution uses the provider-managed **Vertex AI Agent Engine Code Execution** sandbox (`terraform/modules/agent-runtime/`) — hermetic, no bespoke sandbox; VPC-SC perimeter with egress denied by default (`terraform/modules/governance/`). Broker executors are typed, narrow operations, not arbitrary code; `terraform.plan` never applies. **Gap:** runtime code-integrity attestation of the agent itself (ties to ASI03 attestation). |
| **ASI06** | Memory & Context Poisoning | Partial | Vertex Agent Engine **Memory Bank is now wired** in Terraform (`terraform/modules/agent-runtime/main.tf` `context_spec.memory_bank_config`) with generation/embedding models and a **retention `ttl_config`** — bounded-lifetime memories cannot propagate indefinitely across sessions. Untrusted inputs already pass Model Armor + redaction. **Gap:** cross-session/tenant isolation and routing *retrieved* memory back through the input-filter stack are app-layer controls not yet implemented (framework §11.6). |
| **ASI07** | Insecure Inter-Agent Communication | Partial | Today the orchestrator coordinates specialists via shared Pydantic envelopes carrying `agent_identity` + `correlation_id` (`aop_common/schemas.py`); there is no untrusted multi-agent traffic. A2A protocol is not yet wired. **Gap:** signed agent cards at `/.well-known/a2a-agent-card.json`, per-hop server-side authorisation, and OTel trace propagation across the A2A boundary (framework §3.3). (The report itself rates ASI07 as research-stage.) |
| **ASI08** | Cascading Failures | Partial | Single write chokepoint limits blast propagation; dead-letter queues on every `ops.*` topic (`terraform/modules/eventing/`); fail-closed degraded modes (`LIVE_MODE`/`LIVE_SLACK_ENABLED` defaults); idempotency keys (`services/action-broker/idempotency.py`). **Gap:** per-MCP-server circuit breakers and a scheduled reconciliation pass (§13.1/§13.3). |
| **ASI09** | Human-Agent Trust Exploitation | Implemented | The report warns that chain-of-thought is not faithful and that approval prompts become an attack surface under decision fatigue. AOP relies on **verifiable decision transparency**, not CoT: required `Finding.cause_hypothesis` + `Recommendation.rationale` (Pydantic-required), decision records (`policy.py:Decision`), and contextualised out-of-band Slack approvals that the agent cannot self-grant (`services/slack-notifier/`). Approval fatigue is bounded by **risk-tiered routing** — only tier ≥ 3 actions route to humans (`policy/action_classes.yaml`). |
| **ASI10** | Rogue Agents | Partial | Per-agent identity + explicit IAM `run.invoker` allow-list; broker ingress `INTERNAL_LOAD_BALANCER` with authentication required (no exposed runtime); VPC-SC perimeter; SCC v2 + Agent Engine Threat Detection sink (`terraform/modules/governance/`). Halt today is the Slack `Reject` on a pending action. **Gap:** session-level kill-switch (deny all in-flight calls for a session in < 1 min) and automated identity offboarding (ties to NHI1). |

**ASI gaps consolidated (newly surfaced by v2.01):** plan-divergence detection
(ASI01), runtime identity attestation + identity chaining + Agent Naming Service
(ASI03/ASI05), SLSA L3 + image signing + MCP catalogue-drift detection (ASI04),
memory controls when Memory Bank lands (ASI06), A2A agent cards + per-hop authz
(ASI07), per-MCP circuit breakers (ASI08), session-level kill-switch (ASI10).
These extend the §19 open-gaps list below; none are silently deferred.

---

## OWASP Non-Human Identity (NHI) Top 10 crosswalk

v2.01 elevates Agent Identity vs NHI to "the new control plane" and maps agent
risks onto the **OWASP Non-Human Identity Top 10 (2025)**. AOP's static-NHI
hygiene is strong; the dynamic *Agent Identity* layer (attestation, JIT,
chaining, automated lifecycle) is the forward gap.

| NHI | Risk | Status | Implementation & gaps |
|---|---|---|---|
| **NHI1** | Improper Offboarding (ghost agents) | Partial | Per-agent SAs are Terraform-managed and destroyed on decommission (`terraform/modules/agent-runtime/`). **Gap:** automated, ephemeral identity lifecycle — sub-agent identities tied to and revoked at workflow completion (v2.01 "Automated Identity Lifecycle"). |
| **NHI2** | Secret Leakage | Implemented | Secret Manager references only (`aop_common/config.py` holds paths, not values); `auth_token_wo` write-only attribute on the Slack channel; `gitleaks` pre-commit + `secret-scan.yml`; runtime redaction; no secrets in prompts/logs. |
| **NHI3** | Vulnerable Third-Party NHI | Implemented | Managed Google MCP fleet only (no third-party MCP servers/skills); now backed by SBOM + signed provenance + AIBOM and Trivy/dependency-review. |
| **NHI4** | Insecure Authentication | Implemented | WIF / OIDC federation, IAM-bound identities, no exported keys; MCP auth via ADC-derived short-lived bearer tokens (`aop_common/mcp_tools.py`). |
| **NHI5** | Overprivileged NHI | Implemented (static) | Custom roles narrower than predefined; Principal Access Boundary; dataset-scoped BigQuery; tool allow-list ⊆ IAM. **Gap:** consequence-aware / per-principal budgets at runtime (§4.4). |
| **NHI6** | Insecure Cloud Deployment Config | Implemented | Ingress `INTERNAL_LOAD_BALANCER`; VPC-SC + egress denylist; Trivy IaC `config` scan + `tflint` (`.github/workflows/`). |
| **NHI7** | Long-Lived Secrets | Partial | No exported keys; WIF/impersonated credentials per action class (`services/action-broker/impersonation.py`). **Gap:** explicit short-TTL enforcement and ephemeral, just-in-time tokens for the dynamic agent-identity layer. |
| **NHI8** | Environment Isolation | Implemented | Separate dev/prod Terraform roots, projects, and WIF environment bindings (`terraform/environments/{dev,prod}/`, `terraform/bootstrap/`). |
| **NHI9** | NHI Reuse | Implemented | Dedicated SA per agent **and** per action class (`sa-action-<class-slug>`); no identity is shared across agents. |
| **NHI10** | Human Use of NHI (and the reverse) | Implemented | Agents never operate under human identities; the human approver's identity is captured distinctly on delegated actions (`AuditRecord.human_identity`), so logs show both agent and human. |

---

## Runtime governance & regulatory readiness (v2.01 gap register)

v2.01's "From Static Compliance to Runtime Governance" names four capabilities
and a set of compressed reporting timelines. These are tracked here so they are
acknowledged gaps, not oversights (framework §17.2 / §20).

| v2.01 capability | Status | Notes |
|---|---|---|
| Real-time behavioural / plan-divergence monitoring | Gap | Cloud Monitoring alert policies exist (`terraform/modules/observability/`); z-score/χ² baselines and action-sequence-vs-intent divergence are roadmap (§9.2). |
| Consequence-aware authorization | Partial | Policy evaluates action class × env × bounds + approver quorum per event; blast-radius bounds exist (`max_blast_radius`). Per-principal budgets and dynamic blast-radius awareness are the gap. |
| Automated incident classification for compressed timelines (DORA 4 h, NIS2 24 h, NY RAISE 72 h, CA SB 53 15 d) | Gap | SCC findings + threat-detection flow to `ops.signals`; automated severity classification and timeline-aware routing are not yet wired. |
| Trajectory-level explainability | Partial | Per-step rationale + OTel traces (`agents/pyproject.toml`); full transcript replay tool is roadmap (§9.3). |
| Kill switch at agent speed | Partial | Slack `Reject` halts a pending action chain; session-level halt (< 1 min) is roadmap (§14.1). |

---

## Zero Trust for AI Agents crosswalk (Anthropic, 2026)

This section maps AOP to Anthropic's **Zero Trust for AI Agents** brief (2026).
It is **complementary** to the ASI / NHI crosswalks above, not a replacement:
ASI/NHI are *threat* taxonomies; this is the brief's *capability-tier* lens
(**Foundation → Enterprise → Advanced**) plus its central design heuristic.

### The "impossible vs tedious" design test

The brief asks one question of every control: *does this make the attack
impossible, or just tedious?* Friction-only controls (extra hops, rate limits,
approval delays) degrade against an adversary with unlimited patience and
near-zero per-attempt cost. AOP adopts this as a **standing design-review
question** (also enforced in [`DESIGN-REVIEW.md`](./DESIGN-REVIEW.md) and the
PR template). Honest self-assessment of AOP's controls under this test:

- **Impossibility (capability removed):** no exportable SA keys (WIF);
  specialist agents *cannot* write — every mutation goes through the Action
  Broker chokepoint; egress denied by default (VPC-SC); managed Google MCP fleet
  only (no third-party servers).
- **Friction (buys time, not impossibility):** the 15-minute approval window,
  `max_blast_radius` / instance bounds, and policy denial rate. These are
  valuable but are *not* counted as hard barriers — where feasible we prefer a
  control that removes a capability over one that throttles it.

### Capability-tier self-assessment

Status key as elsewhere: `Implemented` · `Partial` · `Gap`. The **AOP tier** is
the brief's tier this domain currently meets; the **Advanced gap** column names
what the next tier would add.

| Brief domain | AOP tier | Status | Implementing surface · Advanced gap |
|---|---|---|---|
| Agent identity & authentication | Enterprise | Implemented | Per-agent SAs + WIF (no static keys); per-action-class short-lived impersonation (`services/action-broker/impersonation.py`). **Advanced gap:** hardware-attested identity + RFC 8693 chaining (ASI03). |
| Access control & least agency | Enterprise | Implemented | Custom roles ⊂ predefined; Principal Access Boundary; deny-by-default policy engine; `max_blast_radius` bounds. **Advanced gap:** JIT auto-expiry on task completion, per-principal budgets, continuous ABAC. |
| Resource boundaries / isolation | Enterprise | Partial | **Identity-based isolation is the primary control** (per-agent identity + `run.invoker` allow-list), which matches the brief's own guidance that network segmentation is a backstop; managed sandbox; VPC-SC. **Advanced gap:** confidential computing, VPC-SC enforced (not dry-run). |
| Observability & auditing | Enterprise | Implemented | OTel + immutable BigQuery + `correlation_id`; **now + dwell-time/coverage metrics and first-pass triage** (`agents/aop_common/triage.py`, `terraform/modules/observability/` `aop_alert_dwell_seconds` / `aop_alert_triage_total` / `detection_dwell_p95`). **Advanced gap:** hash-chained/signed audit, z-score baselines, replay. |
| Input validation & output controls | Enterprise | Implemented | Model Armor `INSPECT_AND_BLOCK` (PI & jailbreak); redaction; structured Pydantic outputs; **now + retrieved-memory re-filtering/spotlighting** (`agents/aop_common/memory.py`). *Constitutional classifiers are Claude-specific — n/a on the Gemini/Model-Armor stack; the equivalent floor filter is in place.* |
| Integrity & recovery | Enterprise | Partial | Version-controlled policy/config; Sigstore-signed SBOM; auto-rollback on post-condition failure. **Advanced gap:** SLSA L3, image signing + Binary Authorization, signed policy files. |
| AI governance policies | Enterprise | Implemented | Policy-as-code (`action_classes.yaml` + `terraform/modules/governance/`); tiered autonomy; named operator roles. **Advanced gap:** policy-compliance metrics emitted from the deploy pipeline. |
| Supply chain (Phase 2) | Enterprise | Partial | CycloneDX + SPDX SBOM, Sigstore provenance, AI-BOM, OpenSSF Scorecard, Trivy + Checkov. **Advanced gap:** SLSA L3, image admission control, dependency-tree redundancy + reachability audit. |
| Memory safeguards (Phase 7) | Enterprise | Partial | **App-layer guard implemented** (`agents/aop_common/memory.py`: cross-session/tenant isolation, content-hash integrity, TTL-at-recall, untrusted re-filtering) + Memory Bank TTL. **Gap:** wire the guard into the Memory Bank store/recall transport. |
| Defensive operations (Part V) | Enterprise | Partial | **Now documented** ([`DEFENSIVE-OPERATIONS.md`](./DEFENSIVE-OPERATIONS.md)): model-at-front-of-queue triage, dwell/coverage targets, MITRE ATT&CK coverage map, 5-incident tabletop, emergency-change procedures. **Advanced gap:** session-level kill-switch *implementation* (design only) and agentic-SOAR auto-response. |

**Tier summary.** AOP is broadly at the brief's **Enterprise** tier with named
**Advanced** gaps. This is a *different scale* from the framework's own maturity
levels (§18), where AOP remains **L1**: L2 graduation is gated by the §19 open
gaps (eval harness, per-principal budgets, hash-chained audit) which the brief's
tiering does not measure. Both scales agree on the forward work.

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
| §7.1 identity | Implemented | Each agent has a dedicated service account (`terraform/modules/agent-runtime/main.tf`): `sa-orchestrator`, `sa-sre`, `sa-devsecops`, `sa-platform`, `sa-finops` — each **bound to its reasoning engine via `spec.service_account`** (+ `roles/aiplatform.user` for model inference, and bucket-scoped `storage.objectViewer` when `agent_artifact_bucket` is set), so the runtime executes under the scoped per-agent identity rather than the shared default Vertex service agent. WIF for CI (`sa-tf-runner-<env>`) with **per-environment principalSet binding** — dev runner is bound to `attribute.repository`, prod runner to `attribute.environment/deploy-prod` so prod impersonation requires a workflow run that opts into a GitHub Environment with manual reviewer gating. The WIF provider's `attribute_condition` additionally fences by `assertion.repository`, `assertion.ref`, and `assertion.event_name`. No exported keys. |
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
| §11.6 conversational memory | Partial | Vertex AI Agent Engine Memory Bank is wired in `terraform/modules/agent-runtime/main.tf` (`context_spec.memory_bank_config`) with generation + embedding models and a **retention `ttl_config`** (`var.memory_default_ttl`, default 30d). **Gap:** user-scoped deletion, cross-session isolation, and re-filtering retrieved memory are app-layer controls still pending. |
| §11.7 data lineage | Gap | Dataplex Data Lineage is documented in `docs/DESIGN-REVIEW.md` Part 8 but not wired in the scaffold. |
| §11.8 DLP and DP | Partial | Sensitive Data Protection wired at the org level via `terraform/modules/governance/`. **FinOps BigQuery surface** is dataset-scoped via `billing_export_bq_dataset_id` (prod) — only the billing export dataset is readable, not every BigQuery dataset in the project. Differential privacy is not applicable — AOP does not serve cohort analytics. |

## §12 — Security

| Sub-section | Status | Implementation |
|---|---|---|
| §12.1 threat model | Implemented | Documented in `docs/DESIGN-REVIEW.md` Part 8.1. |
| §12.2 secret hygiene | Implemented | Secrets in Secret Manager; `auth_token_wo` write-only attribute on the Slack notification channel; pre-commit `gitleaks`. |
| §12.3 supply chain | Partial | Provider pin `~> 7.34` (`terraform/**/versions.tf`); container builds via `services/*/Dockerfile` use uv `--frozen`; SHA-pinned GitHub Actions. **Build-time SBOM** in CycloneDX + SPDX with **Sigstore-signed SLSA build provenance** (`.github/workflows/sbom.yml`); **AIBOM** runtime-composition inventory (`docs/aibom.yaml`). **Gap:** SLSA Level 3, container-image signing + admission control (no image build/push pipeline in this repo yet), MCP tool-catalogue drift detection at session start. |
| §12.4 signed artifacts | Partial | `auth_token_wo` for the Slack token; SBOM artifacts carry a Sigstore-backed provenance attestation (`.github/workflows/sbom.yml`). **Gap:** signed audit exports + policy-file signing are roadmap. |
| §12.5 boundary hardening | Implemented | VPC Service Controls + egress denylist in `terraform/modules/governance/`. |
| §12.6 managed threat detection | Partial | Security Command Center v2 (`google_scc_v2_source` in `terraform/modules/governance/`); SCC findings flow through `ops.signals`. Agent Engine Threat Detection (Preview) feeds the same sink. **Gap:** alerting on agent-specific patterns is not yet tuned. |
| §12.7 red-teaming | Gap | Cadence stated in `docs/DESIGN-REVIEW.md` Part 8.7; operationalisation is the deployer's responsibility today. |
| §12.8 encryption at rest | Partial | All data is encrypted at rest by default with Google-managed AES-256 keys. State buckets additionally use **CMEK** + enforced `public_access_prevention` (`terraform/bootstrap/`). **CMEK for the data plane** (Pub/Sub topics, BigQuery audit dataset + table, Artifact Registry) is a **documented roadmap hardening**, accepted at the scaffold tier via per-resource `checkov:skip` (CKV_GCP_80/81/83/84) — the audit pipeline (`ops.audit`, `audit_events`, `audit_logs`) is the priority surface when CMEK is wired. Other accepted checkov skips are self-documented inline: CKV_GCP_62 (state-bucket access logging redundant with Cloud Audit Data-Access logs), CKV_GCP_117 (`terraform.plan` read-only `roles/viewer`), CKV_GCP_121 (BQ deletion protection is env-driven), CKV_GCP_125 (WIF trust fenced by `assertion.repository`+ref+env). |

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

- [x] Retention policy declared per memory store.
      (`context_spec.memory_bank_config.ttl_config.default_ttl` via
      `var.memory_default_ttl` in `terraform/modules/agent-runtime/`.)
      TTL is now also enforced at *retrieval* time
      (`aop_common/memory.py:MemoryRecord.is_expired`,`prepare_recall`).
- [~] User-scoped deletion procedure tested. App-layer scope binding
      (`aop_common/memory.py:MemoryScope`) identifies a tenant's records
      by construction; the Memory Bank delete transport + procedure test
      remain roadmap.
- [~] Cross-tenant retrieval denied by construction.
      (`aop_common/memory.py:assert_scope_access` + `prepare_recall`,
      unit-tested.) **Gap:** wire the guard into the live recall path.
- [~] Retrieved memory passes through input filters.
      (`aop_common/memory.py:sanitize_retrieved`/`prepare_recall` —
      spotlighting + injection screen, unit-tested.) **Gap:** wire into
      the live recall path.

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

- [x] SBOM generated in NTIA-aligned formats (CycloneDX + SPDX).
      (`.github/workflows/sbom.yml`)
- [x] AIBOM / formal inventory of AI + agentic components maintained.
      (`docs/aibom.yaml` — models, agents, MCP servers, action-class tool
      connectors; validated in CI.)
- [~] SLSA ≥ Level 2. SBOM artifacts carry a Sigstore-signed (keyless OIDC)
      build-provenance attestation via `actions/attest-build-provenance`.
      Extending provenance to container images and reaching **SLSA Level 3**
      is roadmap.
- [ ] Container images signed (Sigstore / cosign / provider-native);
      admission controller verifies before deploy. **Gap** — no image
      build/push pipeline in this repo yet (images built out-of-band).
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
- [x] First-pass triage + dwell-time / coverage instrumented.
      (`aop_common/triage.py`; `aop_alert_dwell_seconds`,
      `aop_alert_triage_total`, and the `detection_dwell_p95` alert in
      `terraform/modules/observability/`. The triage model classifier is
      a skeleton; dwell/coverage stamping and emission are live.)
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
      halts the action chain; session-level halt is *designed* in
      `docs/DEFENSIVE-OPERATIONS.md` §4; implementation is roadmap.
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
      (`services/action-broker/executors/*.py`); the defensive-operations
      runbook (`docs/DEFENSIVE-OPERATIONS.md`) now covers triage, the
      MITRE ATT&CK coverage map, and emergency-change procedures;
      per-incident-class detail is still expanding.
- [ ] Forensic export procedure documented. **Gap** — Roadmap.
- [~] Quarterly DR / kill-switch exercise. Exercise script (five
      simultaneous incidents) documented in `docs/DEFENSIVE-OPERATIONS.md`
      §5; execution cadence operationalised by deployer.

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
4. **Anomaly detectors (z-score / χ²)** (§9.2 / §19 Observability). First-pass
   triage and dwell-time/coverage instrumentation now exist
   (`aop_common/triage.py`, `terraform/modules/observability/`); statistical
   (z-score / χ²) baselines remain.
5. **Session-level kill-switch** (§14.1 / §19 Human oversight). Design specified
   in `docs/DEFENSIVE-OPERATIONS.md` §4; implementation remains.
6. **Memory Bank app-layer controls** (§11.6 / §19 Memory). The app-layer guard
   is now implemented and unit-tested (`aop_common/memory.py`: cross-session /
   tenant isolation, content-hash integrity, TTL-at-recall, untrusted
   re-filtering). Remaining work is wiring the guard into the live Memory Bank
   store/recall transport.
7. **Data lineage** (§11.7 / §19 Data lineage).
8. **SLSA Level 3 + container-image signing/admission + MCP catalogue-drift
   detection** (§12.3 / ASI04). SBOM (CycloneDX + SPDX), Sigstore-signed build
   provenance, and the AIBOM inventory now exist; remaining supply-chain work
   is L3 provenance, image signing at an admission controller, and session-start
   tool-catalogue diffing.
9. **Per-incident-class runbooks + forensic export** (§15.2). The
   defensive-operations runbook (`docs/DEFENSIVE-OPERATIONS.md`) now covers
   triage, the MITRE ATT&CK coverage map, the multi-incident tabletop, and
   emergency-change procedures; per-incident-class detail and the forensic
   export procedure remain.
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
