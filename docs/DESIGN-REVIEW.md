# Agentic Operations Platform — Strategic & Technical Design Review

**Governed multi-agent DevSecOps, SRE and Platform Engineering on Google Cloud**

| | |
|---|---|
| **Document** | Strategic & Technical Design Review |
| **Version** | 1.0 — Draft for Review |
| **Date** | 2026-05-22 |
| **Author** | Platform Architecture |
| **Audience** | Platform owner, prospective DevSecOps / SRE / Platform Engineering functions |
| **Status** | For review and decision |
| **Companion artefacts** | `terraform/` (reference IaC), `agents/` (ADK agent skeletons), `services/` (Slack-notifier & Action Broker skeletons) |

---

## How to read this document

This review has ten parts, matching the commission brief:

1. **Current-state assessment** — *omitted from this public reference; see the note in Part 1.*
2. **Capability review** — the May 2026 Gemini Enterprise / Google Cloud agentic landscape.
3. **Target multi-agent architecture** — the DevSecOps / SRE / Platform operating model.
4. **MCP strategy** — native Google MCP servers and the custom integrations required.
5. **Governance model** — roles, permissions, approvals, policy, audit.
6. **Observability model** — agent- and platform-level monitoring, alerting, and Slack notifications.
7. **Terraform deployment approach** — provider strategy, modules, environments, lifecycle.
8. **Security, compliance, resilience, failure-handling, escalation.**
9. **Roadmap** — near-, medium- and future-term.
10. **Prioritised recommendations** — with rationale, dependencies and risks.

Three appendices hold the raw discovery evidence, the Terraform resource-coverage matrix, and the Slack message contract.

### Maturity legend

Capabilities move fast; every capability claim in Part 2 is tagged:

| Tag | Meaning |
|---|---|
| **GA** | Generally available; safe to build production dependencies on. |
| **Preview** | Public Preview / Pre-GA; usable, but under pre-GA terms — no production SLA. |
| **Announced-GA*** | Stated GA at Google Cloud Next '26 (22–24 April 2026) in launch material; **verify in-console** before committing — launch-post status can precede console availability. |
| **OSS** | Open-source, self-hosted; "not an officially supported Google product". |

### Method and limitations

- **Capability research** was conducted against official Google Cloud documentation, the Google Cloud blog, ADK and A2A release notes, and the HashiCorp Terraform Registry (live provider-schema queries) on 2026-05-22, with deliberate emphasis on the February–May 2026 window (the period after a January 2026 knowledge cut-off, including Google Cloud Next '26).
- Google's April 2026 rebranding means product names are in flux. Where a name changed, both are given. Treat **Announced-GA*** items as planning assumptions, not commitments.

---

## Executive Summary

**The situation.** Greenfield Google Cloud estates that have already started experimenting with agentic capabilities — Vertex AI, Gemini Cloud Assist, Model Armor, the Agent Registry API, the Observability API — typically lack the surrounding **governance scaffolding** an autonomous, action-taking agent framework requires: organisation resource, policy hierarchy, centralised identity, alerting, security-operations tooling. Building agents that can *act* on that kind of foundation, as-is, would be unsafe.

**The opportunity.** The May 2026 Google Cloud agent stack is, for the first time, genuinely production-grade for operations use cases. The managed agent runtime (Vertex AI **Agent Engine**), the **Agent Development Kit (ADK) 2.0** with a graph-based workflow runtime, the **Agent2Agent (A2A)** interoperability protocol, a fleet of **50+ Google-managed MCP servers** that expose Cloud Logging, Monitoring, Trace, GKE, Cloud Run, SecOps and more as governed tools, and native **Gemini Cloud Assist** ops agents (FinOps, infrastructure operations, root-cause Investigations) together make it possible to build a governed DevSecOps / SRE / Platform automation layer **almost entirely from native components**.

**The core recommendation.** Do not build agents first. Build the **foundation and the guardrails** first, then introduce agents in **observe-only** mode, and earn the right to *act* by moving deliberately up a defined autonomy ladder. Specifically:

1. **Establish a governed foundation** — a Cloud Identity / Organisation resource, a folder hierarchy, environment-separated projects, least-privilege IAM, elimination of any exported service-account keys, Terraform-managed from day one.
2. **Stand up the observability and eventing backbone** — alerting, log routing, Security Command Center, Model Armor floor settings, and the Slack notification path — *before* any agent exists.
3. **Introduce agents behind a strict operating model** — a clean separation of **Observe → Recommend → Approve → Act**, where every write action funnels through a single policy-enforcing **Action Broker** and no agent ever holds raw write credentials.
4. **Keep everything model- and tool-agnostic** — ADK's model abstraction, MCP for tools, A2A for agent-to-agent — so new Google capabilities slot in without redesign.

**The headline risks** are (a) acting before the foundation is safe; (b) over-trusting "GA" labels from Next '26 that are not yet real in-console; (c) prompt-injection through poisoned telemetry; (d) unbounded agent cost (Agent Engine Sessions/Memory became billable in early 2026); and (e) approval fatigue degrading into rubber-stamping. Each is addressed in Parts 5–8.

**The path.** A pragmatic 0–3 / 3–9 / 9–18-month roadmap (Part 9) takes the estate from "experimentation" to a governed platform with a full agent roster operating at bounded autonomy. The near-term phase is mostly *remediation and foundation* and delivers value (alerting, security baseline, IaC) even if the agent programme were to stop there.

---

## Part 1 — Current-State Assessment

*Omitted from this public reference. Part 1 is a current-state assessment of
a specific Google Cloud estate; that audit is organisation-specific and is
not part of the framework. The design recommendations in Parts 2-10 are
framework-level and stand alone — they do not depend on the audit findings.*

---

## Part 2 — Gemini Enterprise & Google Cloud Agentic Capabilities Review

This part summarises the **May 2026** state of the relevant Google Cloud agent stack. The defining event of the period is **Google Cloud Next '26 (22–24 April 2026)**, which both consolidated the product naming and shipped a large governance/observability surface for agents.

### 2.1 The 2026 platform consolidation

Two rebrandings matter:

- **October 2025** — *Google Agentspace* became **Gemini Enterprise**, the governed, end-user-facing agentic workspace (an employee-facing app for discovering, building, sharing and running agents over enterprise data).
- **April 2026 (Next '26)** — *Vertex AI* was rebranded the **Gemini Enterprise Agent Platform**; Vertex AI Agent Builder folded in, and **Agent Engine** now surfaces as **"Deployments"** within it. Critically, this is a **branding/packaging change, not an API change** — the underlying `aiplatform.googleapis.com` and `discoveryengine.googleapis.com` APIs, SDKs, billing and **Terraform resources are unchanged** (resources keep `vertex_ai_*` / `discovery_engine_*` names; there is no `google_gemini_enterprise_*` resource).

**The two-layer mental model** to carry through this design:

```
  ┌──────────────────────────────────────────────────────────────┐
  │  GEMINI ENTERPRISE  — governed end-user app / agent gallery   │  ← distribution &
  │  app-level IAM · audit logs · agent sharing · marketplace     │    governance plane
  ├──────────────────────────────────────────────────────────────┤
  │  GEMINI ENTERPRISE AGENT PLATFORM  (formerly Vertex AI)       │  ← build & run plane
  │  Agent Engine runtime · ADK · Sessions · Memory Bank · A2A    │
  └──────────────────────────────────────────────────────────────┘
```

For an *operations* framework, the **Agent Platform** (build/run) is where the agents live; **Gemini Enterprise** (the app) is an optional, later **operator-facing UX surface** — useful for letting humans converse with the agents, not required to run them.

### 2.2 Agent runtime — Agent Engine, Sessions, Memory Bank

**Vertex AI Agent Engine** is the **managed, serverless agent runtime** — the recommended execution substrate for production ops agents. **Status: GA.**

| Component | What it gives an ops framework | Status |
|---|---|---|
| **Agent Engine Runtime** | Serverless runtime; re-engineered for **long-running agents (days), sub-second cold starts, multi-day workflows**. Pricing ~ $0.0864 / vCPU-hour (free tier 50 vCPU-hrs + 100 GB-hrs/month). | **GA** |
| **Sessions** | Short-term, per-conversation/per-incident state. | **GA** — events billable since ~Jan 2026 (~$0.25 / 1,000 events) |
| **Memory Bank** | Long-term, topic-organised memory; auto-curated; "Memory Profiles" for fast recall. Lets agents *learn* the estate over time. | **GA**; **Memory Revisions** (versioned memory) **Preview** |
| **Example Store** | Few-shot example storage to steer behaviour. | GA-track — verify current status |
| **Built-in observability** | Cloud Trace (OpenTelemetry), Cloud Monitoring, Cloud Logging integration. | **GA** |

**Cost is now a first-class design concern.** Sessions, Memory Bank and Code Execution became billable in the January–February 2026 window. A continuously-running ops agent that accumulates memory and events incurs ongoing per-event cost — token/cost budgeting (§6.1) is mandatory, not optional.

**Terraform:** Agent Engine is provisioned by **`google_vertex_ai_reasoning_engine`** (**GA** in `hashicorp/google`). The Memory Bank configuration block (`context_spec`) is **beta-only** — it requires `provider = google-beta`. The core agent (deployment spec, container/source/package specs, ADK `agent_framework`, CMEK `encryption_spec`, PSC interface) is GA.

Agents can alternatively run on **Cloud Run** (more control, container-native) — relevant for components that are not "reasoning engines" (the orchestrator's event handlers, the Action Broker, the Slack-notifier).

### 2.3 Agent Development Kit (ADK) 2.0

**ADK** is Google's **open-source, code-first** toolkit for building, evaluating and deploying agents. It is **model-agnostic** (Gemini and non-Google models) and **deployment-agnostic** (local, Cloud Run, or Agent Engine). For a governed framework that must version-control, code-review and CI-test its agents, **ADK is the recommended build path.**

- **ADK Python 2.0.0 went GA on 19 May 2026** — three days before this review. It introduces a **graph-based Workflow Runtime**: agents, tools and functions are nodes in a workflow graph supporting routing, fan-out/fan-in, loops, retry, **human-in-the-loop** and nested workflows. This is precisely the primitive needed for **deterministic, auditable remediation runbooks**.
- **2.0 is a breaking change** from 1.x (agent API, event model, session schema). Sessions written by 2.0 are readable by ADK ≥ 1.28 but not older 1.x.
- **Languages:** Python, Go, Java and TypeScript all reached **1.0 GA** at Next '26; **Python 2.0** leads. Java/Go/TS 2.0 parity must be verified per language.
- **Deployment:** "ADK Agents on Vertex AI Agent Engine" reached **GA (April 2026)** — ADK agents register to and run on Agent Engine, and can be surfaced in the governed Gemini Enterprise gallery.

**Design implication:** pin ADK exactly (`google-adk==2.x`) — a GA-three-days-ago, breaking-change dependency must not float. Standardise on **Python** for the agents.

### 2.4 Agent2Agent (A2A) protocol

**A2A** is the **open, vendor-neutral protocol for agent-to-agent communication** — discovery, delegation, task hand-off, streaming.

- **Governance:** hosted by the **Linux Foundation**; first stable spec **v1.0**; **150+ supporting organisations** at its one-year mark (April 2026), including Microsoft, AWS, Salesforce, ServiceNow, SAP. (Some secondary sources cite a v1.2 with signed agent cards — treat as **unverified**; v1.0 stable is confirmed.)
- **A2A vs MCP — complementary, not competing.** **MCP = agent-to-tool** (an agent calling an API/database/service). **A2A = agent-to-agent** (agents delegating to one another). **ADK implements both natively.**
- **The canonical pattern for this design:** *A2A between your ops agents; MCP from each agent down to Google Cloud services and custom tools.*

### 2.5 Gemini Cloud Assist — native operations intelligence

**Gemini Cloud Assist** is the **GCP-native operations assistant** and the most directly relevant native product for this framework. At Next '26 it shifted to a **proactive, agentic architecture**:

| Capability | Relevance | Status |
|---|---|---|
| **Infrastructure Operations agents** | Proactive multi-turn agents that troubleshoot/resolve incidents and automate infra ops, driving **`gcloud`, `kubectl`, `Terraform`**. | **Announced-GA*** |
| **FinOps agent** | 24/7 cost-anomaly monitoring; correlates spend spikes to engineering triggers; NL cost reports. | **Announced-GA*** |
| **Cloud Assist Investigations** | The named **root-cause-analysis agent** — parallel analysis across Logging, Asset Inventory, App Hub, Metrics, Error Reporting; ranked "Observations"; probable root causes; can hand off to Google Support. ~19 services covered. | **Preview, access-gated** — since 10 April 2026 requires **Premium Support** or account-team grant |
| **Application Design Center** | NL → architecture; **auto-generates Terraform** to Google best practice; **curated catalogs of pre-approved templates**; SCC policy-compliance integration. | **Announced-GA*** |
| **Cloud Assist as MCP servers** | Cloud Assist's design/ops/troubleshoot/optimise capabilities are **published as MCP servers**, consumable from the Console, Gemini CLI, IDEs and third-party tools. | **Announced-GA*** / Preview |

**Strategic read:** Cloud Assist is best treated as a **capability your agents call**, not a competitor to them. The FinOps agent and Investigations are areas where Google's own agent is mature enough to **adopt directly** rather than rebuild. **However:** Investigations is Preview *and* access-gated — confirm Premium Support eligibility early; its programmatic REST/Terraform surface is **not clearly documented**, so the **MCP server route is the concrete integration path** today.

### 2.6 Agentic SOC — Google Security Operations agents

Google's "agentic SOC" puts Gemini-native agents inside **Google Security Operations (SecOps)** and **Security Command Center**:

| Agent / capability | Relevance to the DevSecOps agent | Status |
|---|---|---|
| **Triage & Investigation Agent (TIN)** | Autonomous alert triage — YARA-L searches, Mandiant threat-intel enrichment, command-line de-obfuscation, process-tree reconstruction, **True/False-Positive verdicts with confidence**. Cuts ~30-min triage to ~60s. HITL by design. | **Public Preview**; **GA targeted 2026**; free trial Apr–Jun 2026 for eligible SecOps tiers |
| **Threat Hunting Agent** | Proactively surfaces evasive attack patterns. | Shipped — verify status |
| **Detection Engineering Agent** | Finds detection-coverage gaps; auto-generates detections. | Shipped — verify status |
| **SCC agentic risk/threat detection** | "Agent Security dashboard" (powered by SCC); AI-risk and AI-threat widgets; SCC's **AI Protection integrates with Agent Engine** to detect agentic threats (rogue access, exfiltration). | **Announced-GA*** — verify per-feature |

These are the **security-side counterparts** to Cloud Assist's ops agents. The DevSecOps agent in this design **consumes SecOps/SCC** rather than re-implementing triage.

### 2.7 The native MCP server fleet

The most important platform shift of the period: **every Google Cloud service is now "MCP-enabled by default."** Google operates **50+ managed remote MCP servers** at globally consistent `https://<service>.googleapis.com/mcp` endpoints, governed by **native IAM** (including **IAM Deny**, fail-closed), with **nothing to host** ("available for everyone", announced 29 April 2026).

Servers directly relevant to this framework (status from the MCP Supported Products page, verified 2026-05-22):

| MCP server | Endpoint | Status | Used by |
|---|---|---|---|
| Cloud Logging | `logging.googleapis.com/mcp` | **GA** | SRE, DevSecOps, Platform |
| Cloud Monitoring | `monitoring.googleapis.com/mcp` | **GA** | SRE, all |
| Cloud Trace | `cloudtrace.googleapis.com/mcp` | **GA** | SRE |
| Error Reporting | `clouderrorreporting.googleapis.com/mcp` | **GA** | SRE |
| GKE | `container.googleapis.com/mcp` | **GA** | SRE, Platform |
| Cloud Run | `run.googleapis.com/mcp` | **GA** | SRE, Platform |
| Compute Engine | `compute.googleapis.com/mcp` | **GA** | Platform |
| Resource Manager | `cloudresourcemanager.googleapis.com/mcp` | **GA** | Platform, governance |
| Cloud Asset Inventory | `cloudasset.googleapis.com/mcp` | **Preview** | Platform, DevSecOps |
| Google Security Operations | `chronicle.<region>.rep.googleapis.com/mcp` | **GA** | DevSecOps |
| Pub/Sub | `pubsub.googleapis.com/mcp` | **GA** | eventing / all |
| BigQuery | `bigquery.googleapis.com/mcp` | **GA** | FinOps |
| Network Intelligence Center | `networkmanagement.googleapis.com/mcp` | **GA** | SRE, Platform |
| Agent Registry | `agentregistry.googleapis.com/mcp` | **Preview** | governance |
| Gemini Cloud Assist | `geminicloudassist.googleapis.com/mcp` | **Preview** | SRE, FinOps |

Two naming clarifications for this review: there is **no MCP server branded "Security Command Center"** (SecOps/Chronicle is the security MCP server; SCC powers the Agent Security dashboard instead); and the "observability MCP" is **three** servers — Logging, Monitoring, Trace.

Self-hosted alternatives exist — the **`gcloud-mcp`** OSS repo (four servers: `gcloud`, `observability`, `storage`, `backupdr`) and the **MCP Toolbox for Databases** (OSS, v1.3.0, 20+ databases) — but both carry "not an officially supported Google product" / "preview, may break" language. **Prefer the managed fleet; reserve self-hosted for gaps.** (See Part 4.)

### 2.8 Governance & security primitives for agents

Next '26 shipped the governance surface that makes *action-taking* agents defensible:

| Primitive | What it does | Status |
|---|---|---|
| **Agent Identity** | SPIFFE-based **cryptographic identity** per agent (`spiffe://…`), X.509 cert auto-rotated every 24h, tokens cert-bound. Usable directly as an IAM `principal://`. **Cannot be shared, cannot impersonate, no long-lived keys.** | **Preview** (Pre-GA terms) |
| **IAM + Principal Access Boundary (PAB)** | PAB caps the **resource set** an identity may reach *regardless of granted roles* — hard containment for autonomous agents. Simplified predefined agent roles; re-auth for sensitive actions. | **GA** (PAB); agent-role simplifications **Announced-GA*** |
| **Model Armor** | Inline screening of prompts/responses **and MCP traffic** — prompt-injection, jailbreak, sensitive-data, malicious-URL. Enabled via **floor settings** (project/folder/org minimum). | **GA**; MCP integration documented (label unstated — verify) |
| **VPC Service Controls** | Perimeter around Vertex AI / agent APIs — a hard data-exfiltration boundary. | **GA**; agent-identity-in-VPC-SC **Preview** |
| **Agent Registry / Agent Gateway** | Central library of approved agents/tools/MCP servers; unified fleet control point with Model Armor inline. | **Announced-GA*** |
| **Cloud Audit Logs for agents** | With Agent Identity, when an agent acts on a user's behalf, logs record **both** the agent's and the user's identity — forensic attribution of autonomous actions. | **GA** |

**Two caveats carried into the design.** (1) Agent Identity — the cleanest identity model — is **Preview**; the design uses it where available but keeps **dedicated, least-privilege service accounts + PAB** as the GA-grade fallback for production-critical paths. (2) Model Armor only screens **supported Google MCP servers** and only does **basic** DLP — any third-party/custom MCP server **bypasses it**, so custom MCP servers (Part 4) need their own input hygiene.

### 2.9 Observability & evaluation for agents

| Capability | Detail | Status |
|---|---|---|
| Agent Engine built-in metrics | **Only four** auto-collected on `ReasoningEngine`: request count, request latency, container CPU time, container memory time. **Error rate, token usage and tool-call counts are NOT built in** — they must be custom/log-based metrics. | **GA** |
| Cloud Trace + OpenTelemetry | ADK ≥ 1.17 emits OTel traces/logs to Cloud Observability automatically — prompts, responses, token usage, tool calls, latency, errors. | **GA** |
| Gen AI / agent observability in Cloud Monitoring | Application Monitoring aggregates traces via OTel GenAI semantic conventions — model-call counts, token usage, latency. | GA-track — verify |
| Gen AI Evaluation Service | Evaluates **final response and trajectory** (the tool-call/reasoning path): `trajectory_exact_match`, `_in_order_match`, `_precision`, `_recall`. **This is how you regression-test "did the agent take the right steps."** | **Public Preview** |
| Agent cost / token spend | **No turnkey per-agent cost meter.** Token usage via traces; dollar cost via Cloud Billing + BigQuery export; per-agent attribution needs **custom log-based metrics keyed on agent identity**. | — |

**Design implication:** budget explicit engineering effort for **custom metrics** (error rate, token spend per agent, tool-call rate, policy exceptions) and adopt **trajectory evaluation as the CI regression gate** for agents.

### 2.10 Maturity snapshot — what to rely on now

| Build on now (GA) | Use with care (Preview) | Treat as roadmap (Announced-GA* / verify) |
|---|---|---|
| Agent Engine runtime; Sessions & Memory Bank | Cloud Assist Investigations (also access-gated) | Cloud Assist FinOps / Infra-Ops agents |
| ADK 2.0 (Python); A2A v1.0 | Agent Identity (SPIFFE) | Agent Registry / Agent Gateway |
| Managed MCP fleet (Logging, Monitoring, Trace, GKE, Run, SecOps, Pub/Sub, BigQuery…) | Gen AI Evaluation Service; Agent Registry MCP | SCC Agent Security dashboard |
| Model Armor; IAM + PAB; VPC-SC; Cloud Audit Logs | SecOps TIN; Model Armor↔MCP | Agent Evaluation / Simulation / Optimizer |
| Native Slack notification channel; Pub/Sub; Eventarc | Cloud Asset Inventory MCP | A2A vendor-partner registrations |
| Terraform `google` 7.33 — agent, observability, security resources | Memory Revisions | — |

**The conclusion for this estate:** the *load-bearing* parts of the architecture in Part 3 — Agent Engine, ADK, MCP fleet, Model Armor, IAM/PAB, VPC-SC, Pub/Sub/Eventarc, the Slack path, and the Terraform surface — are **all GA today**. The Preview items (Agent Identity, Gen AI Evaluation, Investigations) are **enhancements, not foundations**: the design adopts each behind a feature flag with a GA fallback, so nothing on the critical path depends on a pre-GA capability.

---

## Part 3 — Target Multi-Agent Architecture

### 3.1 Design principles

The architecture is held to ten principles. Every choice in §3–§8 is traceable to one of them.

1. **Native-first.** Prefer Google-managed components (Agent Engine, managed MCP servers, Cloud Monitoring, SCC, Eventarc). Custom code exists only where there is no native equivalent (Action Broker, Slack-notifier, the OpsSignal normaliser).
2. **Model-agnostic.** Agents are written against the ADK abstraction. The default model (e.g. Gemini 3 Pro) is **configuration, not code** — swapping in Anthropic / OpenAI / a future Gemini is a config change.
3. **Tool-agnostic.** All tool access is via **MCP**. No agent imports a Google client library directly.
4. **Agent-agnostic at the boundary.** Inter-agent communication is **A2A**. A future externally-built agent (an outsourced SOC, a vendor FinOps agent) drops in without code change.
5. **Decision/execution separation.** Specialist agents **decide and recommend**; only the **Action Broker** executes. No agent holds raw write IAM on Google Cloud.
6. **Policy-driven autonomy.** The autonomy level *per action class, per environment* is **declarative policy** (Rego / typed rules), not code. Tightening or loosening agent autonomy is a config change, version-controlled and reviewable.
7. **Default-safe.** Default action is **recommend**. Default approval is **required**. Default on policy-engine failure is **deny**. Default on health regression after action is **rollback**.
8. **Event-driven.** Pub/Sub is the spine; everything has a topic, a schema and a DLQ.
9. **Observable by construction.** Every decision, recommendation, approval and action emits a structured record. No invisible work.
10. **Cost-aware.** Each agent has a **token / cost budget** with hard caps and alerts. The platform fails the agent's call before the cost target breaches.

### 3.2 The operating model — *Observe → Recommend → Approve → Act*

This is the brief's required separation, formalised as the **lifecycle of every operational event**:

| Phase | What happens | Who does it | Default outcome |
|---|---|---|---|
| **Observe** | Signal arrives; normalised to `OpsSignal`; deduplicated; correlated; enriched with context; classified for severity and domain. | Orchestrator + native sources | Either *dropped (noise)* or *routed* |
| **Recommend** | Domain specialist reasons over the signal, produces a `Finding` (cause hypothesis, impact, confidence) and one or more `Recommendations` (each a typed action with a proposed autonomy tier). | One specialist agent (SRE / DevSecOps / Platform / FinOps) | A `Finding` published; Slack notification rendered |
| **Approve** | The Action Broker evaluates each `Recommendation` against policy: auto-approve (Tier 2), Slack-approve (Tier 3), executive-approve (Tier 4) or deny. | Action Broker + Policy Engine + human approver(s) | An `ActionRequest` becomes `Approved`, `Denied` or `Expired` |
| **Act** | Action Broker executes the approved action through least-privilege APIs, verifies post-conditions, and either confirms or auto-rolls-back. | Action Broker | `ActionExecuted` + audit record |

Every transition is an **event on Pub/Sub** (`ops.signals` → `ops.findings` → `ops.actions.requested` → `ops.actions.approved` → `ops.actions.executed`) and **every transition produces an immutable audit row in BigQuery**. The Slack channel only ever shows phase transitions — never raw logs.

### 3.3 Autonomy tiers and action classes

Autonomy is **per action class, per environment** — not a per-agent setting. The same agent may have Tier 2 authority for "scale a Cloud Run service within bounds in `dev`" and Tier 1 only for "rotate a Secret Manager secret in `prod`."

| Tier | Name | Behaviour | Default eligibility |
|---|---|---|---|
| **0** | Observe | Read-only; no `Recommendation` produced beyond a `Finding` and a Slack info. | Always |
| **1** | Recommend | Specialist proposes a typed action; Slack message includes the action but **no Approve button**; humans execute out-of-band. | Default for any new action class |
| **2** | Act (guarded) | Action Broker executes within declarative bounds (range limits, frequency caps, blast-radius caps); verifies post-condition; auto-rollback on regression. | After ≥30 days of clean Tier-1 history *and* an approved policy |
| **3** | Act (Slack-approved) | Slack message has Approve/Reject; two-approver threshold for prod; timeout → expire (safe-default). | After Tier 2 maturity for a related action class, or as the initial tier for higher-impact actions |
| **4** | Act (autonomous, bounded) | Fully autonomous with kill-switch, hard rate-limit, mandatory rollback hooks, and quarterly review. | Rare — narrowly scoped, well-understood remediation only |

**Canonical action-class catalogue (extract):**

| Action class | Dev default | Prod default | Reversible? |
|---|---|---|---|
| `cloud_run.scale_within_range` | Tier 2 | Tier 2 | Yes |
| `cloud_run.restart_revision` | Tier 2 | Tier 3 | Yes |
| `cloud_run.rollback_to_previous` | Tier 2 | Tier 3 | Yes |
| `gke.cordon_drain_node` | Tier 2 | Tier 3 | Partially |
| `iam.disable_service_account_key` | Tier 2 | Tier 2 | Yes |
| `iam.add_role_binding` | Tier 1 | Tier 1 | Yes (Tier-1 only — too sensitive) |
| `firestore.delete_collection` | Tier 1 | Tier 1 | No (never auto) |
| `secret_manager.disable_version` | Tier 2 | Tier 3 | Yes |
| `workflows.run` (`*-dryrun`) | Tier 2 | Tier 2 | Yes |
| `workflows.run` (production) | Tier 3 | Tier 3 | Depends |
| `terraform.plan` | Tier 2 | Tier 2 | Yes (no apply) |
| `terraform.apply` | Tier 3 | Tier 4 (with full guardrails) | Depends |
| `scc.mute_finding` | Tier 2 | Tier 3 | Yes |
| `cost.shrink_idle_resource` | Tier 2 | Tier 3 | Yes |
| `incident.escalate_to_human` | Tier 0/1 (always allowed) | Tier 0/1 | n/a |

This catalogue lives in the policy repo and is versioned. Promotion (e.g., moving `cloud_run.scale_within_range` from Tier 1 to Tier 2 in prod) is a **policy pull request with two reviewers** — not an agent decision.

### 3.4 Agent roster

Five specialists plus an orchestrator. Each is a separate ADK 2.0 Python project, deploys to **Agent Engine** as a "Deployment" (reasoning engine), and carries its **own dedicated service account** (today) and **own SPIFFE Agent Identity** (when GA).

```
                       ┌────────────────────────────┐
                       │     OPS ORCHESTRATOR       │
                       │   (duty manager / hub)     │
                       └─┬──────┬──────┬──────┬─────┘
                  A2A    │      │      │      │
              ┌──────────┘      │      │      └──────────┐
              ▼                 ▼      ▼                 ▼
        ┌─────────┐       ┌─────────┐ ┌─────────┐  ┌──────────┐
        │   SRE   │       │ DevSec  │ │Platform │  │  FinOps  │
        │  Agent  │       │   Ops   │ │ Engr.   │  │  Agent   │
        └─────────┘       └─────────┘ └─────────┘  └──────────┘
                                  │
                                  ▼ MCP
                        ┌──────────────────┐
                        │  Action Broker   │   (the only writer)
                        └──────────────────┘
```

| Agent | Mandate | Primary MCP tools | Typical findings |
|---|---|---|---|
| **Ops Orchestrator** | Receives every signal; deduplicates and correlates; assigns to a specialist; **owns the Slack conversation** for the incident; runs the incident lifecycle through to closure; the **only** agent operators talk to. | Pub/Sub, Cloud Logging (correlation queries), Firestore (incident store), Slack-notifier (custom MCP) | "These three alerts are one incident"; "this is an SRE-Platform joint"; "we need a Tier-3 approval" |
| **SRE Agent** | Reliability — latency, error rate, saturation, SLO burn, deploy-related regressions, dependency outages, capacity. | Cloud Logging, Monitoring, Trace, Error Reporting MCP; **Gemini Cloud Assist** MCP (incl. Investigations when Premium-eligible); GKE / Cloud Run MCP for read | "P99 latency 4× baseline on `<svc>` since deploy `<id>`; suspect `<config>`; recommend Tier-3 rollback" |
| **DevSecOps Agent** | Security — SCC findings, IAM drift, key exposure, vulnerability, supply-chain, Model Armor signals, policy violations. | **SecOps / Chronicle** MCP; SCC findings (via Eventarc); Cloud Audit Logs; Asset Inventory MCP; Resource Manager MCP | "Service-account key created outside Terraform; auto-disable proposed (Tier-2)"; "Critical SCC finding cluster, escalation" |
| **Platform Engineering Agent** | Drift, deployment health, IaC state, resource hygiene, network/config compliance. | Cloud Asset Inventory MCP; Resource Manager; Cloud Build; Cloud Deploy; **Terraform plan** via Action Broker | "10 resources drifted from declared state in `<env>`; `terraform plan` shows non-destructive diff; recommend Tier-3 apply" |
| **FinOps Agent** | Cost — anomalies, budget burn, waste, rightsizing. Wraps the native Cloud Assist FinOps agent when available. | **BigQuery** MCP (billing export); **Recommender** API; **Gemini Cloud Assist FinOps** | "Spend +42% MoM in `<project>`; root cause: `<resource>`; recommend Tier-2 shrink in dev / Tier-3 in prod" |

A **Knowledge / Runbook Agent** is an optional sixth — a RAG agent over runbooks and post-mortems (via Vertex AI Search / Discovery Engine). It is not strictly required for the initial roll-out and is listed under Roadmap (§9).

### 3.5 Topology and coordination

- **A2A** is the protocol between Orchestrator and specialists, and between specialists when one needs another (the SRE agent asking the Platform agent "is there a recent deploy on this service?"). ADK's `AgentCard` describes each agent's capabilities; the Orchestrator routes via skill match plus declared domain.
- **MCP** is how every agent reaches **tools** — both the Google managed fleet (read-only telemetry, observability, registries) and **custom MCP servers** (Part 4) for organisation-specific lookups and the **Action Broker** itself.
- **Pub/Sub** is the **event spine**. Eventarc bridges native sources (Monitoring alerts, SCC findings, Cloud Audit Logs via log-sink, Cloud Build status, Cloud Deploy rollouts, Eventarc Advanced asset-change feeds) into the normalised `ops.signals` topic. Every step in the lifecycle emits an event; every event has a DLQ and a retry budget.
- **Firestore** holds incident state — the Orchestrator's session, the open findings, the action ledger pointer. It is the durable cross-agent state store.
- **BigQuery** holds the **immutable audit stream** (`ops.audit` topic → BQ subscription → partitioned, append-only table) — the source of truth for compliance, replay and evaluation.

### 3.6 Reference architecture (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SIGNAL SOURCES                                                             │
│  Cloud Monitoring alerts · Security Command Center findings · Audit Logs    │
│  Eventarc (asset & deploy events) · Cloud Build · Cloud Deploy              │
│  Cloud Scheduler scans · Agent self-emit (synthetic checks, eval failures)  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  normalised  OpsSignal
                                   ▼
                       ┌───────────────────────┐
                       │  Pub/Sub  ops.signals │  (+ DLQ)
                       └───────────┬───────────┘
                                   ▼
                ┌──────────────────────────────────┐
                │       OPS ORCHESTRATOR (ADK)     │  dedup · correlate · route
                │       Vertex AI Agent Engine     │  owns Slack incident thread
                │       deployment "orchestrator"  │
                └──┬──────┬──────┬──────┬──────────┘
                A2A│      │      │      │
              ┌────┘      │      │      └────┐
              ▼           ▼      ▼           ▼
         ┌────────┐  ┌────────┐ ┌────────┐ ┌────────┐
         │  SRE   │  │DevSec  │ │Platform│ │ FinOps │   each on Agent Engine
         │ Agent  │  │  Ops   │ │  Engr  │ │ Agent  │   own SA / Agent Identity
         └───┬────┘  └───┬────┘ └───┬────┘ └───┬────┘
             │MCP        │MCP       │MCP       │MCP
             ▼           ▼          ▼          ▼
   ┌─────────────────────────────────────────────────────┐
   │  GOOGLE-MANAGED MCP FLEET                            │
   │  Logging · Monitoring · Trace · Error Reporting      │
   │  GKE · Cloud Run · Compute · Resource Manager        │
   │  SecOps · Asset Inventory · Pub/Sub · BigQuery       │
   │  Network Intelligence Center · Gemini Cloud Assist   │
   └─────────────────────────────────────────────────────┘
                         │
                         │  recommend → request action
                         ▼
   ┌────────────────────────┐          ┌─────────────────────────┐
   │     ACTION BROKER      │ ◄────────┤   POLICY ENGINE         │
   │  custom MCP on Run     │          │  Rego rules + tier map  │
   │  - identify caller     │          └─────────────────────────┘
   │  - policy check        │
   │  - approval flow ──────┼──► Pub/Sub  ops.actions.requested
   │  - rate-limit / quota  │      │
   │  - idempotency key     │      ▼  Slack approve/reject
   │  - execute (least-priv)│   Pub/Sub  ops.actions.approved
   │  - post-condition      │      │
   │  - auto-rollback       │      ▼
   │                        │   Pub/Sub  ops.actions.executed
   └──────────┬─────────────┘
              │ least-priv writes via dedicated SA per action class
              ▼
   ┌─────────────────────────────────────────────────────┐
   │   GOOGLE CLOUD APIs (write)                          │
   │   No agent holds these grants — only the Broker.     │
   └─────────────────────────────────────────────────────┘

   ┌────────────────────────┐         Pub/Sub  ops.notifications
   │   SLACK NOTIFIER       │ ◄──────────────────────────────────
   │   Cloud Run service    │   OpsNotification → Block Kit
   │   Slack Interactivity  │ ──► Pub/Sub  ops.actions.approved
   │   approve/reject UI    │
   └────────────────────────┘

   ┌────────────────────────────────────────────────────┐
   │   AUDIT  &  EVAL                                    │
   │   Pub/Sub ops.audit → BigQuery (immutable, partit.) │
   │   Cloud Trace + OpenTelemetry (ADK 1.17+)           │
   │   Custom log-based metrics (token, error, policy)   │
   │   Gen AI Evaluation Service (trajectory CI gate)    │
   └────────────────────────────────────────────────────┘
```

### 3.7 Control plane / data plane

- **Control plane** (governs *what* happens): Orchestrator, Action Broker, Policy Engine, Agent Registry (Google managed when GA + a local Firestore catalogue today), Slack approval surface, audit ledger.
- **Data plane** (does the *work*): the four specialist agents, MCP tool calls, Pub/Sub flows, the Slack-notifier renderer.

The control plane is **tighter, more restricted, more audited**. It runs in its own project (`ops-agents-prod`) under tighter Org Policy. The data plane scales out; the control plane is small and reviewed.

### 3.8 Future-readiness — what we deliberately do **not** hard-code

- **No hard-coded model.** Each agent declares `model: <env-config>`; the production default is set in one place. Swapping to a new Gemini, or to Anthropic via ADK's model adapter, is a config change with a CI eval gate.
- **No hard-coded tools.** Every tool is wired in via MCP. New managed Google MCP servers (e.g., when the SCC MCP server ships) drop in through the agent's `mcp_servers` list.
- **No hard-coded autonomy.** Autonomy is declarative policy; tier promotions are PRs.
- **No hard-coded agent set.** The Orchestrator routes by **declared skills** (A2A `AgentSkill`s) — adding a sixth agent or replacing one with a vendor agent is a registry entry.
- **No bespoke event format.** `OpsSignal` / `Finding` / `ActionRequest` / `ActionExecuted` are versioned JSON Schemas; consumers handle the version they understand.

The single most important future-readiness statement: **everything new on the Google roadmap (Agent Identity GA, Agent Registry MCP GA, SCC Agent Security dashboard, A2A vendor partners, ADK 3.x, new MCP servers) plugs into the existing seams without redesign.** Where a Preview capability is used today, the same seam already accepts the GA-only fallback.

---

## Part 4 — MCP Strategy: Native and Custom

### 4.1 The MCP rule of thumb

> Read with managed MCP. Act through the Action Broker. Look up org-specific context through Apigee MCP or a small custom MCP server.

### 4.2 Native managed MCP servers to consume

Every read-side capability is taken from the **Google-managed remote MCP fleet** (Part 2.7). Wiring is per-agent and declarative — the agent declares which MCP servers it needs and the platform mounts them.

| Agent | Managed MCP servers consumed |
|---|---|
| Orchestrator | Cloud Logging (correlation), Pub/Sub, Resource Manager |
| SRE | Cloud Logging, Monitoring, Trace, Error Reporting, GKE, Cloud Run, Network Intelligence Center, **Gemini Cloud Assist** (incl. Investigations when entitled), **Developer Knowledge** (official docs lookup) |
| DevSecOps | **Google Security Operations** (Chronicle), Cloud Asset Inventory, Resource Manager, Cloud Logging (audit), Compute (firewall reads), **Developer Knowledge** (security / IAM guidance lookup) |
| Platform | Cloud Asset Inventory, Resource Manager, GKE, Cloud Run, Compute, Cloud Build / Cloud Deploy (via APIs), **Developer Knowledge** (resource-pattern docs) |
| FinOps | **BigQuery** (billing export queries), Recommender, **Gemini Cloud Assist** (FinOps agent surface), **Developer Knowledge** (Billing / Recommender API docs) |

For the four Preview / Announced-GA* MCP servers (Cloud Asset Inventory, Agent Registry, Gemini Cloud Assist, MCP integrations in Model Armor), the platform wires them behind a feature flag and a fallback: e.g., Asset Inventory MCP unavailable → fall back to the **`google_cloud_asset` Terraform-defined exports** consumed via BigQuery.

### 4.3 Custom MCP servers (built by us)

Three custom MCP servers are part of the design. Each runs on **Cloud Run** (the documented hosting pattern), behind **IAM** for service-to-service auth, with **Workload Identity Federation** (no SA keys), and is itself an asset under Terraform management.

| Custom MCP server | Why it must be custom | Tools exposed |
|---|---|---|
| **Action Broker MCP** | There is no native "policy-gated write" surface. This is the single execution choke point. | `propose_action(class, target, params)`, `request_approval(action_id)`, `execute(action_id, approval_token)`, `rollback(action_id)`, `status(action_id)` |
| **Runbook & Knowledge MCP** | RAG over org-specific runbooks, post-mortems, ADRs. | `search_runbook(query)`, `get_runbook(id)`, `latest_postmortem(service)` |
| **Org Context MCP** | Look-ups specific to the estate that no managed server provides: project↔owner mapping, service↔team mapping, environment classification, change-freeze calendar. | `owner_of(project)`, `team_for(service)`, `is_change_freeze(at, env)`, `service_criticality(service)` |

A fourth "MCP-equivalent" is **Apigee MCP** — for any *existing internal API* (e.g., a future ServiceNow/Jira integration), Apigee MCP turns the API into a governed MCP tool with **no code change**, using OAuth 2.1 + OIDC. This is the recommended path the day a non-Google internal API needs to be agent-callable.

### 4.4 MCP hosting, security, lifecycle

- **Hosting:** Custom MCP servers run on **Cloud Run v2** in the `ops-agents-prod` (and `-dev`) project. Each server is a separate revision-managed service with its own service account.
- **AuthN/AuthZ:** Service-to-service calls use Cloud Run **IAM (`run.invoker`)** with the *calling agent's* service account / Agent Identity. **OAuth 2.1 + OIDC** when called from outside the trust boundary (e.g., Gemini CLI, IDEs). MCP `tools/call` payloads include the caller's identity for audit.
- **Input hygiene:** Managed Google MCP servers are protected by **Model Armor floor settings** (`--add-integrated-services=GOOGLE_MCP_SERVER`, mode `INSPECT_AND_BLOCK`) — but **custom MCP servers bypass Model Armor**. Each custom MCP server therefore implements its **own input validation, schema validation, output redaction** and length limits, and treats every input as **untrusted** including tool outputs from upstream calls (poisoned-log defence).
- **Lifecycle:** All custom MCP servers are **Terraform-managed** (`modules/action-broker`, `modules/slack-notifier`, etc., with a generic `mcp-server` sub-module pattern). Container images are built in Cloud Build, stored in Artifact Registry, and **Binary Authorization** enforces signed-image policy in prod.

### 4.5 MCP server registry / catalogue

Until **Agent Registry MCP** is GA-stable in-console (it is currently **Preview**), the platform maintains a **lightweight Firestore-backed catalogue** of available MCP servers: name, endpoint, IAM identity required, owner, status, schema URL, last health check. Agents discover servers from the catalogue; the catalogue is itself behind an `Org Context MCP` tool (`list_mcp_servers(agent_role)`). When Agent Registry MCP matures, the platform migrates with no agent-side change — the catalogue API is the abstraction.

---

## Part 5 — Governance Model

### 5.1 Roles and RACI

The framework recognises five operational roles. In a small team one person may hold several; the *roles* still exist independently for audit purposes.

| Role | Responsibilities | RACI on agent action |
|---|---|---|
| **Platform Owner** | Owns the platform; sets autonomy policy; approves Tier-4. | A |
| **SRE / On-call** | Approves Tier-3 reliability actions; investigates incidents; closes them. | R / A (Tier 3 reliability) |
| **DevSecOps Reviewer** | Approves Tier-3 security actions; reviews SCC findings. | R / A (Tier 3 security) |
| **Approver (second)** | Provides the second approval in prod for two-approver actions; rotates. | R |
| **Auditor / Compliance** | Reviews the audit ledger; quarterly tier-promotion review; eval scorecard sign-off. | C / I |

Today's estate has **one human principal** holding all roles. The design names the roles separately so the *workflow* exists, ready for additional humans to slot in. Critically, **the Platform Owner must not also be the only Approver** — the very next hire / second account should claim Approver to give meaningful separation of duties.

### 5.2 Identity model

The identity model has two epochs.

**Today — GA fallback (and the basis on which production launches):**

- Each agent has a **dedicated, named service account** (e.g., `sa-orchestrator@`, `sa-sre@`, `sa-devsecops@`). Naming standard: `sa-<component>-<env>@<project>.iam.gserviceaccount.com`.
- Each SA's permissions are **assembled from explicit role grants on explicit resources** — no `roles/editor`, no project-level primitive grants.
- **Principal Access Boundary (PAB)** caps the **resource scope** an SA can ever reach, regardless of role grants, by project / by resource label / by region. PAB is the **hard backstop** for "this agent must never touch prod."
- **Workload Identity Federation** drives CI; no exported SA keys exist anywhere (R2).
- **Org Policy** `iam.disableServiceAccountKeyCreation = enforced` in the agent projects so a future operator cannot accidentally regenerate the very keys we removed.

**Future — Preview path (adopted as it GAs):**

- Each agent additionally gets a **SPIFFE Agent Identity** (`spiffe://agents.<org>/...`), used directly as the IAM principal where supported.
- 24h auto-rotated X.509; tokens cryptographically bound to the cert; **non-shareable and non-impersonating** — the structural fix for "an agent's credential getting reused elsewhere."
- For human-on-behalf actions, Cloud Audit Logs record **both** the agent's and the user's identity — the single most important governance feature when autonomous actions touch production.

### 5.3 Permissions matrix (extract)

Read-only managed-MCP access is permissive within an agent's domain. **Write access is concentrated in the Action Broker.**

| Agent SA / identity | Grants (project-scoped, PAB-bounded) |
|---|---|
| `sa-orchestrator` | `roles/logging.viewer`, `roles/monitoring.viewer`, `roles/pubsub.subscriber` on event topics, `roles/pubsub.publisher` on action/notification topics, `roles/datastore.user` (Firestore), `roles/iam.serviceAccountTokenCreator` on its own SA only |
| `sa-sre` | `roles/logging.viewer`, `roles/monitoring.viewer`, `roles/cloudtrace.user`, `roles/errorreporting.viewer`, `roles/run.viewer`, `roles/container.viewer` |
| `sa-devsecops` | `roles/securitycenter.findingsViewer`, `roles/chronicle.viewer`, `roles/logging.privateLogViewer`, `roles/iam.securityReviewer`, `roles/cloudasset.viewer` |
| `sa-platform` | `roles/cloudasset.viewer`, `roles/resourcemanager.projectViewer`, `roles/cloudbuild.builds.viewer`, `roles/clouddeploy.viewer` |
| `sa-finops` | `roles/bigquery.dataViewer` (billing dataset only), `roles/recommender.viewer` |
| `sa-action-broker` | The **only** SA with write grants — and they are partitioned per action class via **bound, short-lived impersonation** (`generateAccessToken`) of *narrower* per-action SAs (e.g., `sa-action-cloudrun-scale`). The Broker holds no broad write IAM directly. |

Result: even if a specialist agent is fully compromised (prompt-injected, model jailbreak), the **worst it can do is recommend** — not write.

### 5.4 Approval workflows

- **Tier 2 (auto):** policy-gated; the Action Broker logs the policy decision and proceeds. No human-in-the-loop, but always Slack-announced **after** the fact for awareness, and an Auditor can revoke retroactively.
- **Tier 3 (Slack-approved):** Slack message with Approve / Reject buttons; **one approver in dev, two distinct approvers in prod**; **15-minute default approval window** (configurable per action class); expiry → action denied; the *requesting* agent never approves; approver identity captured from Slack OAuth.
- **Tier 4 (executive-approved):** Tier-3 plus an out-of-band confirmation (a one-time code via a separate channel — e.g., email or a Cloud Identity push) and a mandatory **post-execution review** entry.
- **Change-freeze override:** an Org Context policy can mark periods (deployment freezes, weekend embargo, etc.) — during freeze, Tier 2 actions degrade to Tier 3 and Tier 3 to Tier 4. Hard-coded calendar; auditable.

### 5.5 Policy as code

Policy lives in a separate Git repo (or directory) under the same Terraform pipeline. Two layers:

1. **Action-class policy (Rego / typed Python rules):** defines, per action class × environment, the autonomy tier, bounds (e.g., scale range, max blast radius), allowed time windows, rate limits, and required approver count. Evaluated by the **Policy Engine** inside the Action Broker before every action.
2. **Org Policy + Model Armor floor settings + SCC custom modules:** the **preventative** layer — enforced *by Google Cloud* below the Broker. Examples enforced at folder/org scope:
   - `iam.disableServiceAccountKeyCreation = enforced` (kill the key-sprawl class of finding)
   - `gcp.resourceLocations` (`in:eu-locations`) for production data
   - `compute.requireOsLogin`
   - `iam.allowedPolicyMemberDomains` (when an org is established)
   - Model Armor floor: minimum prompt-injection, sensitive-data and malicious-URL screening for all integrated MCP servers in prod.
   - Custom SCC module: alert when a service-account key is created (defence in depth against the policy).

The CI for policy changes runs **`gcloud beta terraform vet`** plus the Broker's own policy unit tests; **no policy change can ship without two reviewers and a green test run.**

### 5.6 Audit and traceability

Every event in the lifecycle (signal, finding, recommendation, approval request, approval decision, execution, post-condition check, rollback) writes a structured **`AuditRecord`** to the `ops.audit` Pub/Sub topic with these mandatory fields:

```jsonc
{
  "audit_id": "uuid",
  "correlation_id": "incident-or-signal-id",
  "timestamp": "RFC3339",
  "phase": "signal|finding|recommendation|action_requested|action_approved|action_executed|rollback",
  "agent_identity": "spiffe://… or sa email",
  "human_identity": "user email (when present)",
  "environment": "dev|prod",
  "domain": "sre|devsecops|platform|finops",
  "action_class": "...",
  "policy_decision": { "tier": 3, "rule": "...", "outcome": "approved|denied|expired" },
  "evidence_refs": ["log://...", "trace://...", "dashboard://...", "scc://..."],
  "model": { "id": "gemini-3-pro", "tokens_in": 12340, "tokens_out": 567 },
  "outcome": { "status": "...", "rollback": false, "verification": {...} }
}
```

A Pub/Sub **BigQuery subscription** lands these directly in a partitioned, append-only `audit.events` table — schema-evolved via Pub/Sub schemas. Query and retention policies are managed in Terraform. The audit table is the **source of truth** for compliance, eval-data extraction and replay.

### 5.7 Governance lifecycle — onboarding a new agent or action class

A short, mandatory ritual replaces ad-hoc agent additions:

1. **Define** the agent's purpose, signals, declared skills (A2A `AgentCard`), MCP servers consumed, and SA identity (PR to the agent repo).
2. **Threshold** the autonomy — default Tier 1 for every new action class.
3. **Pilot** for ≥30 days at Tier 1 in `dev` with the eval gate (Gen AI Evaluation Service trajectory metrics) running in CI.
4. **Promote** by policy PR to Tier 2 in `dev`; auditor sign-off.
5. **Promote** by policy PR to Tier 2 / Tier 3 in `prod` after additional clean window.
6. **Review** quarterly — every Tier-2+ action class is re-justified, with the audit table as evidence.

The same ritual in reverse for retirement: deprecate → demote tiers → disable → archive.

---

## Part 6 — Observability Model

### 6.1 Agent-level observability — the nine dimensions

The brief names nine dimensions. Each is mapped to a concrete mechanism:

| Dimension | How it is measured | Where it shows up |
|---|---|---|
| **Health** | Agent Engine built-in: `request_count`, `request_latencies`, `cpu_allocation_time`, `memory_allocation_time` on `aiplatform.googleapis.com/ReasoningEngine`. Liveness checked by a synthetic ping signal published every 60s and a "synthetic ping" agent skill that must respond. | Per-agent dashboard "Health" row; "Agent down" alert |
| **Activity** | Cloud Trace (OTel) span counts per agent; `agent.session.count` log-based metric. | Dashboard "Activity"; weekly digest |
| **Decisions** | Every `Finding` and `Recommendation` written to `ops.audit` → BigQuery; logged as a structured Cloud Logging entry with `agent.decision_id`, `confidence`, `rationale_hash`. | BigQuery `audit.decisions` view; dashboard "Decisions per hour" |
| **Failures** | Log-based metric on `severity=ERROR` from agent logs + Pub/Sub DLQ depth on `ops.signals.dlq`, `ops.findings.dlq`, `ops.actions.*.dlq`. | "Agent error rate" alert (warn > 1%, page > 5%); DLQ-depth alert |
| **Regressions** | **Gen AI Evaluation Service** (trajectory metrics: `trajectory_exact_match`, `_in_order_match`, `_precision`, `_recall`) runs in CI on every agent change and **nightly online eval** on a sampled 1% of prod traffic. Tracked over time. | Dashboard "Eval score"; alert on >5% drop week-over-week; PR gate |
| **Token usage** | Custom log-based metric extracting `model.tokens_in/tokens_out` from agent logs (ADK OTel emits this); per-agent counter and per-action distribution. **No turnkey meter exists** (Part 2.9). | Dashboard "Tokens by agent / day"; budget burn alert |
| **Action outcomes** | Action Broker emits `ops.actions.executed` with `outcome.status` and `outcome.rollback`. Log-based metric → success rate, rollback rate. | Dashboard "Action success"; alert on rollback-rate spike |
| **Latency** | Agent Engine `request_latencies` + Cloud Trace end-to-end span (signal-in → action-executed). | Dashboard "Decision latency p50/p95/p99"; SLO |
| **Policy exceptions** | Action Broker logs `policy_decision.outcome=denied`. Log-based counter. | Dashboard "Policy denials"; alert on spike (possible misconfig or attack) |

### 6.2 Platform-level observability

The platform rollup aggregates agent metrics into **estate-wide** views:

- **Estate health score** — composite of agent uptime, eval score, action success rate, alert volume.
- **MTTR (signal-to-resolution)** by domain and severity.
- **Cost per incident** (token spend + executor compute cost) attributed via audit correlation IDs.
- **Coverage map** — which Google Cloud resources have ≥1 agent observing them (via Cloud Asset Inventory crossed with the signal sources). Gaps become roadmap items.
- **Approval throughput** — Tier-3 approvals/day, median time-to-approve, expiry rate (high expiry rate → workflow problem).

### 6.3 Dashboards

Four standard `google_monitoring_dashboard` resources, JSON-defined and Terraform-managed:

1. **`agent-health-<agent>`** — one per agent. Health row, activity, eval, error rate, token spend, latency p50/p95/p99, action outcomes (where applicable), policy denials.
2. **`ops-platform-overview`** — estate health, MTTR by domain, signal volume, action volume by tier, cost per incident, approval throughput.
3. **`finops-overview`** — billing-export-backed; spend MoM, by project, by service, top movers, FinOps agent's open findings.
4. **`action-audit`** — actions in flight, approved/rejected/expired counters, rollback events, top action classes.

Dashboards are **read-only in prod** (Org Policy on dashboard edits) — changes go through Terraform.

### 6.4 Alerting

All alerts are `google_monitoring_alert_policy` resources. Severity drives **routing**, not just colour.

| Alert | Condition | Severity | Routing |
|---|---|---|---|
| Agent down | `up{agent=…} == 0` for 5m | **Critical** | Slack `#ops-incidents` (page) + Pub/Sub redundant path |
| Agent error rate | > 5% over 10m | **High** | Slack `#ops-incidents` |
| Decision latency p95 > 60s | rolling 15m | **High** | Slack `#ops-incidents` |
| Eval score drop > 5% WoW | nightly | **High** | Slack `#ops-eval` |
| Token budget burn > 80% of monthly | once | **Medium** | Slack `#ops-finops` |
| Action rollback rate > 5% (7-day) | once | **High** | Slack `#ops-incidents` + Auditor email |
| Policy denial spike | > 3σ above 14-day baseline | **Medium** | Slack `#ops-security` |
| DLQ depth > 0 | any | **High** | Slack `#ops-incidents` |
| SCC critical finding | `severity=CRITICAL` | **Critical** | Slack `#ops-security` + Pub/Sub redundant |
| Cost anomaly (FinOps agent) | finding | **Medium** | Slack `#ops-finops` |

**Resilience note:** Slack, Cloud Mobile App, Webhooks and PagerDuty notification types share **one internal Google delivery service** — a single point of failure for paging. Every **Critical** alert therefore has a **redundant Pub/Sub channel** so that an out-of-band consumer can re-page on different infrastructure.

### 6.5 Logging and traceability

- **Structured JSON logs everywhere.** Agents log `correlation_id`, `signal_id`, `finding_id`, `action_id`, `agent_identity`, `policy_decision`, `model.tokens_*`.
- **Trace propagation.** ADK ≥ 1.17 emits OTel spans; `correlation_id` flows as a baggage item from `OpsSignal` → Orchestrator → specialist → Action Broker → Slack-notifier. A single click in Slack lands in the trace.
- **Log routing.** A single `google_logging_project_sink` exports all `_AllLogs` from agent projects to a centralised `audit` BigQuery dataset (and to a GCS bucket for **immutability with Object Lock-style retention**) — replacing today's "only `_Default`/`_Required`" posture.
- **Retention.** Audit retained 7 years (configurable); operational logs 90d hot + 1y cold.

### 6.6 Slack operational notifications — the message contract

Every Slack message is rendered by the **Slack-notifier** service from a typed **`OpsNotification`** event. The schema directly satisfies the brief's required fields:

```jsonc
// OpsNotification v1 — published to Pub/Sub topic  ops.notifications
{
  "schema": "ops.notification.v1",
  "notification_id": "ntf_2026-05-22T07:14:33Z_abc123",
  "correlation_id": "inc_2026-05-22_001",
  "produced_at": "2026-05-22T07:14:33Z",
  "severity": "high",            // info|low|medium|high|critical
  "environment": "prod",         // dev|prod
  "domain": "sre",               // sre|devsecops|platform|finops|orchestrator

  // The brief's required fields, exactly:
  "summary": "P99 latency on payments-api is 4.2× baseline since 06:58 BST; ~38% of checkout requests affected.",
  "affected_component": {
    "type": "cloud_run_service",
    "name": "payments-api",
    "project": "ops-target-prod",
    "region": "europe-west2"
  },
  "impact": "Operational: ~38% of /v1/checkout requests above 2s; estimated business impact: degraded checkout for ~12% of users in EU. SLO error-budget burn rate 8× target.",
  "likely_cause": "Strong correlation with deploy `rev-payments-api-00081-x9` at 06:55 BST (Δ=3 min); config diff increased pool size beyond DB ceiling. (Confidence: 0.78)",
  "recommended_actions": [
    {
      "id": "act_001",
      "label": "Roll back payments-api to rev-00080-7q",
      "action_class": "cloud_run.rollback_to_previous",
      "tier": 3,                  // requires approval in Slack
      "estimated_duration_s": 45,
      "reversible": true
    },
    {
      "id": "act_002",
      "label": "Open Cloud Assist Investigation for full RCA",
      "action_class": "cloud_assist.start_investigation",
      "tier": 2,
      "estimated_duration_s": 300,
      "reversible": true
    }
  ],
  "human_required": true,        // true if any action needs Tier-3+ approval
  "approval_window_until": "2026-05-22T07:29:33Z",
  "references": {
    "logs":      "https://console.cloud.google.com/logs?...",
    "dashboard": "https://console.cloud.google.com/monitoring/dashboards/...",
    "trace":    "https://console.cloud.google.com/traces/...",
    "runbook":  "https://runbooks.example.org/payments-api/latency",
    "scc":      null,
    "ticket":   "https://jira.example.org/browse/INC-12345",
    "workflow": "https://console.cloud.google.com/workflows/...rollback"
  },
  "agent": {
    "identity": "spiffe://agents.example/sre",
    "model":    "gemini-3-pro",
    "tokens":   { "in": 8420, "out": 612 },
    "trace_id": "1f4e..."
  }
}
```

Block Kit rendering (sketch):

```
┌───────────────────────────────────────────────────────────────┐
│ 🟥  HIGH · SRE · prod                              inc_2026-…  │
│ payments-api · europe-west2                                    │
├───────────────────────────────────────────────────────────────┤
│ P99 latency on payments-api is 4.2× baseline since 06:58 BST;  │
│ ~38% of checkout requests affected.                            │
│                                                                │
│ *Impact* — degraded checkout for ~12% of EU users; SLO burn 8× │
│ *Likely cause* — deploy rev-00081-x9 at 06:55 (Δ=3m).          │
│ *Confidence* — 0.78                                            │
├───────────────────────────────────────────────────────────────┤
│ *Recommended next step*                                        │
│ Roll back payments-api to rev-00080-7q (Tier 3, ~45s, reversible)│
│ [ Approve rollback ]   [ Reject ]   [ Open RCA Investigation ] │
│                                                                │
│ Approval window expires in 14m 27s.                            │
├───────────────────────────────────────────────────────────────┤
│ 📜 Logs · 📈 Dashboard · 🔍 Trace · 📖 Runbook · 🎫 INC-12345 │
└───────────────────────────────────────────────────────────────┘
```

**Operational design principles for the message:**

- **Human-readable summary first.** No JSON, no log lines, no raw Stackdriver IDs in the visible message body.
- **Impact in business / operational terms** — never just "metric X over threshold."
- **Confidence is stated explicitly** — a 0.78 confidence is not the same as a 0.95.
- **Only one or two recommended actions visible**; further actions in a thread reply.
- **Approval window is shown as a live countdown** (Slack message edit on a 30s tick).
- **Every reference is a deep link** — clicking "Logs" lands in the correlated Cloud Logging query, "Dashboard" lands on the time-windowed dashboard, "Runbook" lands in the relevant runbook.
- **No PII / no secrets** in the message — Slack-notifier runs the OpsNotification through a Model Armor sanitisation step before posting; "redacted" markers replace sensitive substrings.
- **Channel discipline**: `#ops-incidents` (Critical/High operational), `#ops-security` (DevSecOps), `#ops-finops` (FinOps), `#ops-eval` (regressions), `#ops-platform` (drift), `#ops-audit` (after-the-fact Tier-2 actions). Channel choice is part of the contract, not free-form.

### 6.7 Reporting

- **Daily digest** — one Slack post per channel at 09:00 local with overnight findings, top action classes, eval status, cost burn.
- **Weekly platform report** — auto-generated to a docs bucket and posted in `#ops-platform`: estate-health score trend, MTTR, top-5 noisy signals (and what was done about them), action-class promotion candidates, eval-regression list.
- **Monthly governance review** — auditor-led: tier-promotion proposals, policy-change PRs of the month, SA/identity drift report, key/secret hygiene, residency compliance.
- **Quarterly tier-promotion review** — every Tier-2+ action class is reviewed against the audit ledger; promote / hold / demote.

---

## Part 7 — Terraform Deployment Approach

### 7.1 Provider strategy

| Choice | Value | Why |
|---|---|---|
| Provider | **`hashicorp/google` 7.x** (`~> 7.33`) as primary | Latest stable 7.33.0; major 7.0 GA'd Oct 2025; weekly releases mean tight minor pinning is essential |
| Beta | **`hashicorp/google-beta` 7.x** (same line) | Used **only** where a required field is beta-gated — currently the **`context_spec`** (Memory Bank) on `google_vertex_ai_reasoning_engine`, and any future beta-only agent fields |
| Terraform CLI | **`>= 1.15`** | Native GCS state locking (≥1.10); `identity` import block (≥1.12); `_wo` write-only attrs (≥1.11) |
| Alternative | **OpenTofu 1.11+** consuming the same provider | Valid drop-in if open-source/MPL-2.0 license matters; do not mix CLIs across the same state |
| Lockfile | `.terraform.lock.hcl` committed and reviewed | Automate version-pin bumps with Renovate/Dependabot — weekly cadence makes manual tracking impractical |
| Reusable modules in this repo | **looser** constraints (`>= 7.0`); **no** `provider` or `backend` blocks | Best practice: root pins, modules don't |
| Registry modules consumed | Major-version pinned (`~> 18.0`) | Cloud Foundation Toolkit modules are versioned semver |

**Beta usage discipline:** every `provider = google-beta` instance carries an inline comment explaining the field that requires it and a TODO referencing the upstream issue / expected GA. We **never** use google-beta as a default — only as a surgical exception.

### 7.2 Repo & module structure

The scaffolded layout (under `agentic-ops-platform/terraform/`):

```
terraform/
├── bootstrap/                 # one-time, run by hand; creates the state bucket + WIF
│   ├── main.tf
│   ├── versions.tf
│   └── README.md
├── modules/
│   ├── foundation/            # org/folder/project structure, baseline IAM, billing wiring, essential contacts
│   ├── governance/            # Org Policy, SCC v2, Model Armor floorsetting + templates, custom roles, audit sinks
│   ├── eventing/              # Pub/Sub topics & schemas, DLQs, Eventarc triggers, BigQuery audit subscription
│   ├── observability/         # Dashboards, alert policies, notification channels (incl. Slack), log sinks, log-based metrics, SLOs
│   ├── agent-runtime/         # google_vertex_ai_reasoning_engine per agent, dedicated SAs, IAM, PAB
│   ├── action-broker/         # Cloud Run v2 service, IAM, per-action-class impersonation SAs, secrets
│   └── slack-notifier/        # Cloud Run v2 service, Pub/Sub push subscription, secrets, IAM
└── environments/
    ├── dev/
    │   ├── backend.tf         # state in gs://<org>-tfstate-dev/aop/
    │   ├── versions.tf
    │   ├── providers.tf
    │   ├── main.tf            # composes modules with dev variables
    │   └── terraform.tfvars
    └── prod/
        ├── backend.tf         # state in gs://<org>-tfstate-prod/aop/
        ├── versions.tf
        ├── providers.tf
        ├── main.tf
        └── terraform.tfvars
```

Three structural rules:

1. **Modules never configure providers or backends.** Roots do.
2. **Files stay under ~500 lines**; split by concern, not by alphabet.
3. **`terraform-docs`** generates each module's `README.md` from variables/outputs on commit — no hand-maintained module documentation.

### 7.3 Environment separation

**Directories, not workspaces.** `dev/` and `prod/` are separate root modules with separate backends, separate state, separate WIF pool/provider, separate target projects, and separate variables. Workspaces share one backend and one set of credentials — they blur the prod/non-prod boundary, which a governed framework cannot accept.

| Aspect | Dev | Prod |
|---|---|---|
| GCP project | `ops-agents-dev` (target) | `ops-agents-prod` (target) |
| State bucket | `gs://<org>-tfstate-dev/aop/` | `gs://<org>-tfstate-prod/aop/`, separate CMEK key |
| CI identity | WIF pool `ci-dev`; SA `tf-runner-dev` | WIF pool `ci-prod`; SA `tf-runner-prod`; two-approver protected branch |
| Provider version | May lead prod by one minor — used to validate upgrades | Lags one minor behind dev for the first 2 weeks |
| Autonomy policy | Tiers 0–2 default | Tier 1 default; Tier 2/3 by explicit policy entry |
| Model Armor mode | `INSPECT_AND_BLOCK` (matches prod, to surface issues early) | `INSPECT_AND_BLOCK` enforced |
| Org Policy | `gcp.resourceLocations = in:eu-locations` (recommendation) | `gcp.resourceLocations = in:eu-locations`, `iam.disableServiceAccountKeyCreation = enforced`, `compute.requireOsLogin = enforced` |

### 7.4 State and backend

- **GCS backend**, one bucket per environment, **versioning on**, **CMEK** with per-environment keyrings.
- **Native locking** — Terraform ≥ 1.10 / OpenTofu ≥ 1.11 use GCS object-generation locking; **no separate Firestore lock table is required** (older guidance is obsolete).
- **State bucket IAM** is the tightest in the repo: `tf-runner-<env>` SA only, plus a break-glass `tf-emergency` SA disabled by default.
- **State bucket lives behind VPC-SC** when the perimeter is established (Phase 2 — §9).
- **Bootstrap is a one-time, hand-run module** (`bootstrap/`) that creates the bucket, the CMEK key, the WIF pool and the runner SA. It commits *only its own* state to a local backend; subsequent modules pick up the remote backend it just created.

### 7.5 Lifecycle and CI/CD

The CI pipeline (GitHub Actions or Cloud Build — both supported; GHA shown for brevity) is the **only** legitimate way to apply Terraform to dev/prod. Humans do not run `terraform apply` from laptops.

```
   PR opened
     │
     ▼
   ┌─ fmt + tflint + tfsec ─┐  ←─ fails block merge
   │                        │
   ├─ terraform validate    │
   │                        │
   ├─ terraform plan (dev)  │     plan JSON posted to PR + uploaded to GCS
   │                        │
   ├─ gcloud beta terraform vet  ←─ Google's native policy gate
   │                        │
   ├─ OPA / Conftest        ←─ project-specific policy rules
   │                        │
   ├─ cost estimation       │     Infracost-style — informational
   │                        │
   ├─ trajectory eval       ←─ for agent-config changes only
   │                        │
   └─ require ≥2 reviewers (CODEOWNERS for prod)
         │
         ▼  merge to main
   ┌─ apply (dev) ─┐
   │  WIF → tf-runner-dev  │
   │  state-locked         │
   └───────────────────────┘
         │
         ▼  (manual gate: deploy-to-prod label)
   ┌─ apply (prod) ─┐
   │  WIF → tf-runner-prod │
   │  two-approver enforced│
   │  rollback plan saved  │
   └───────────────────────┘
```

Notable choices:

- **No exported SA keys, ever.** CI authenticates via **Workload Identity Federation**.
- **`gcloud beta terraform vet`** is the *native* policy gate; OPA/Conftest covers org-specific rules the vet library cannot express.
- **The plan JSON is durable** — uploaded to GCS, retained 90d. It is part of the audit ledger.
- **Drift detection** is a scheduled `terraform plan` (read-only) every 6h; non-empty diffs publish an `OpsSignal` to the Platform agent.
- **`deletion_policy = "PREVENT"`** is set on production `google_vertex_ai_reasoning_engine`, `google_discovery_engine_*`, and the audit `google_pubsub_topic` resources — a hard guard against accidental destruction.
- **Secrets never live in state.** Slack OAuth token uses `sensitive_labels.auth_token_wo` (write-only); pair with `auth_token_wo_version` for rotation.

### 7.6 Resource coverage and gaps

The Terraform surface is broad and well-aligned to this architecture. The summary (full matrix in Appendix B):

| Component | Coverage | Tag |
|---|---|---|
| Vertex AI Agent Engine | `google_vertex_ai_reasoning_engine` | **GA** (Memory Bank `context_spec`: **beta-only**) |
| Cloud Run (agents, broker, notifier) | `google_cloud_run_v2_service` / `_job` / `_worker_pool` + `_iam_*` | **GA** |
| Pub/Sub spine | `google_pubsub_topic` / `_subscription` / `_schema` + `_iam_*` | **GA** |
| Eventarc | `google_eventarc_trigger`, `_message_bus`, `_pipeline`, `_enrollment` | **GA** |
| Monitoring | `google_monitoring_dashboard` / `_alert_policy` / `_notification_channel` / `_slo` | **GA** |
| Native Slack channel | `google_monitoring_notification_channel { type = "slack" }` with `sensitive_labels.auth_token_wo` | **GA** |
| Logs routing & metrics | `google_logging_project_sink`, `_metric`, `_log_view`, `_log_scope` | **GA** |
| Secret Manager | `google_secret_manager_secret` / `_secret_version` (+ regional) | **GA** |
| Model Armor | `google_model_armor_template`, `google_model_armor_floorsetting` | **GA** |
| Security Command Center | `google_scc_v2_*` (organization/folder/project source, mute, notification, BQ export) | **GA** — standardise on `_v2_*` |
| VPC Service Controls | `google_access_context_manager_*` (incl. `_dry_run_*`) | **GA** |
| Org Policy | `google_org_policy_policy`, `google_org_policy_custom_constraint` | **GA** |
| IAM | `_project_iam_member`/_binding/_policy, custom roles, `_service_account_iam_*` | **GA** — prefer `_iam_member` (additive) |
| Discovery Engine (if Gemini Enterprise app surface adopted) | 16 `google_discovery_engine_*` resources | **GA** |
| Artifact Registry + Binary Authorization | `google_artifact_registry_*`, BinAuthz policy | **GA** |
| CFT modules to use | `terraform-google-modules/project-factory` 18.2.0, `…/network` 18.1.0, `…/iam`, `…/log-export`, `…/org-policy`, `…/vpc-service-controls` | **GA, ≥1.0** |

**Gaps to acknowledge (and how this design handles them):**

1. **No `google_vertex_ai_model`** for generic custom-model registration. Models are uploaded out-of-band; Terraform manages the **serving topology** (endpoints, deployment specs). Agent model choice is *configuration*, not a Terraform-managed model registration.
2. **No `google_gemini_enterprise_*`** — the Gemini Enterprise *app* (gallery, Agent Designer) is **not Terraform-manageable** today. Surface configuration is via Console / API. The design treats Gemini Enterprise as an **optional UX layer** added later (§9) and not on the critical path.
3. **No public Terraform surface for Cloud Assist Investigations.** Investigations are invoked via API/MCP; **the Terraform module sets up the *integration* (the Cloud Assist MCP IAM, the Premium Support entitlement reference)**, not the investigation itself.
4. **Agent Identity (SPIFFE)** Terraform surface is **Preview-quality** and incomplete; the design uses dedicated service accounts as the GA baseline and migrates to Agent Identity per project as it stabilises in the provider.
5. **`agentregistry.googleapis.com`** is API-enabled in the estate but the Terraform resource set is sparse today. The platform's own Firestore catalogue (Part 4.5) is the abstraction; no migration disruption when Agent Registry resources mature.

---

## Part 8 — Security, Compliance, Resilience, Failure-Handling, Escalation

### 8.1 Security architecture (defence in depth)

| Layer | Control | Implementation |
|---|---|---|
| **Identity** | One identity per agent; PAB resource cap; no SA keys | Dedicated SAs (GA) → Agent Identity (Preview); WIF for CI; `iam.disableServiceAccountKeyCreation` enforced |
| **Network** | Custom-mode VPC; private Google access; (later) VPC-SC perimeter | Replace `default` VPC; perimeter for `ops-agents-prod` + the audit BQ dataset; `_dry_run_*` variants used to stage |
| **Data** | CMEK everywhere; Secret Manager for all secrets; write-only secret attrs | Per-environment keyrings; `_wo` for Slack token; **no plaintext in state** |
| **Model & tool I/O** | Model Armor floor settings; output redaction in Slack-notifier; structured tool calls only | Floor mode `INSPECT_AND_BLOCK` for prod; **custom MCP servers do their own input hygiene** since Model Armor does not cover them |
| **Action** | Action Broker is the only writer; per-action-class impersonation; idempotency; rate limit | Bounded `generateAccessToken` on narrow SAs; idempotency key = `correlation_id + action_class + target` |
| **Supply chain** | Pinned ADK (`google-adk==2.x`); signed images; SBOM | Artifact Registry; **Binary Authorization** in prod; `cosign` signatures; `containerscanning` enabled |
| **Audit** | Immutable BQ audit ledger; Cloud Audit Logs retained ≥1y; Access Transparency where eligible | Pub/Sub → BQ subscription; folder-level log sink; retention via Terraform |
| **Detection** | SCC v2 enabled; Event Threat Detection; custom SCC modules | Custom module: alert on SA-key creation; alert on agent role-binding writes outside Terraform |

### 8.2 Compliance

- **Today:** no formal regulatory regime applies to this estate. The framework is therefore aligned to **Google Cloud's Recommended AI Controls framework**, **CIS Google Cloud Foundations Benchmark**, and **NIST AI RMF** as design anchors. Each is treated as a *checklist*, not a *certification*.
- **Data residency:** the platform owner is UK-based with a GBP billing account. **Standardise on `europe-west2` (London)** for all data and compute, with `eu` multi-region for storage/BigQuery. Mixed residency in the current estate (`nam5` Firestore, `us-central1` Workflows) is acknowledged as a migration item (R6). Note Agent Engine region availability — confirm `europe-west2` is in the supported region set at deployment time, otherwise use `europe-west4` (Netherlands) as a fallback in-jurisdiction.
- **Model Armor cross-region caveat:** Model Armor may forward inspection cross-region; document this as a known data-handling fact in the residency statement.
- **Audit retention:** 7 years for audit, 1 year for operational logs, 90 days for traces — Terraform-managed.
- **Forward path:** the design does not preclude SOC 2 / ISO 27001 — every control mapped above produces evidence in the audit ledger.

### 8.3 Resilience and failure handling

The platform must **fail safe** — failure of any component must not enable an unintended action.

| Failure | Behaviour |
|---|---|
| Agent crash / unavailable | Pub/Sub queues backlog; orchestrator surfaces "agent down" within 60s; specialist's signals are *not* auto-handled by another agent (no privilege blurring) |
| Action Broker unavailable | All Tier 2/3/4 actions **fail closed** — Tier 1 (recommend) continues; Slack notification states the degradation; operator can act manually |
| Policy Engine unavailable | **Default-deny**; Action Broker refuses all requests with reason `policy_engine_unavailable` |
| Model provider outage / quota exhaustion | ADK model adapter falls back to declared secondary; if no secondary, agent enters **safe-degraded** mode (Tier 0 only) |
| Memory Bank corruption / drift | Memory Revisions (when GA) restored; until then, Memory Bank is treated as cache — disable, run from raw signals |
| Pub/Sub delivery failure | DLQs catch; alert raised; Slack `#ops-incidents` notified; replay tool re-injects from DLQ |
| Slack outage | Cloud Mobile / PagerDuty redundant channel for Critical alerts; OpsNotifications retained in `ops.notifications.dlq` and replayed when Slack recovers |
| Approval window expiry | Action **denied** — never silently applied |
| Post-action health regression | **Auto-rollback** triggered by Broker's post-condition check (default for Tier 2/3); rollback failure escalates to Critical |
| Runaway agent (cost/token blowout) | Per-agent monthly token budget enforced by log-based metric + alert + Broker circuit-breaker → agent throttled at 80% / blocked at 100% |
| Action loop (A → B → A) | Idempotency key prevents same action being executed twice; orchestrator detects loops via correlation graph; agent quarantined |

### 8.4 Agent threat model

The DevSecOps agent's first job is to defend the framework itself. The named threats:

| Threat | Mitigation |
|---|---|
| **Indirect prompt injection** (poisoned log line, ticket body, telemetry) | Model Armor floor for managed MCP traffic; custom MCP servers sanitise; **agent LLM never produces commands directly — only structured `Recommendation` JSON validated by the Broker** |
| **Model jailbreak / harmful response** | Model Armor inspects responses; structured-output schema (`Recommendation`) rejects non-conforming output; Slack-notifier additionally redacts |
| **Over-privileged agent** | Decision/execution split; PAB; dedicated SA per agent; quarterly access review |
| **Compromised model provider** | ADK abstraction allows swap; eval gate catches behavioural drift; provider-side anomaly via SCC AI Protection (when GA) |
| **Memory poisoning** | Memory Bank treated as cache, not source of truth; Memory Revisions (Preview); periodic memory eval |
| **Supply-chain attack on ADK / containers** | Pinned exact versions; signed images; Binary Authorization; SBOM tracked; `containerscanning` |
| **Approval fatigue / spoofing** | Rate-limit Tier-3 approval prompts per approver; require two distinct approvers in prod; verify approver Slack identity via Slack OAuth → Cloud Identity match |
| **Action loop / amplification** | Idempotency key; max-attempts per `correlation_id`; quarantine on threshold breach |
| **Token theft** | Cert-bound tokens via Agent Identity (when GA); short-lived SA tokens; never log tokens; Model Armor redaction |
| **Denial-of-wallet (token DoS)** | Per-agent hard token caps; budget burn alerts at 50/80/100%; circuit breaker |
| **Lateral movement from compromised agent** | PAB resource caps; VPC-SC perimeter; SCC AI Protection threat detection (Announced-GA*) |

### 8.5 Escalation model

A single escalation matrix, SLA-driven, channelled through the Orchestrator:

| Severity | Ack SLA | Initial response SLA | Resolution target | Routing |
|---|---|---|---|---|
| Critical | 5 min | 30 min | 4 h | Slack #ops-incidents *with* page (redundant Pub/Sub path); after 5min unacked → secondary page; after 15min → Platform Owner |
| High | 15 min | 1 h | 8 h | Slack #ops-incidents; on-call rotation |
| Medium | 1 h | 4 h | 2 business days | Slack channel by domain |
| Low | 1 day | 5 business days | best effort | Slack daily digest |

Escalation paths are **policy-configurable** (an OnCall directory in the policy repo), and the Orchestrator is responsible for **driving** the escalation timer — not the human. Every escalation step itself becomes an `AuditRecord`.

---

## Part 9 — Roadmap

Three horizons. Each phase delivers value even if the next one is deferred.

### Phase 1 — Foundation (months 0–3)

*Goal: a governed, observable Google Cloud foundation that is safe to host agents on. Agents arrive at the end of this phase, in observe-only mode.*

**Deliverables:**

- **F1. Establish Cloud Identity & Organisation.** Free-tier Cloud Identity → an Organisation resource → folder hierarchy (`shared/`, `dev/`, `prod/`). Migrate any existing projects in (R1).
- **F2. IAM remediation.** Eliminate any exported service-account keys; replace with WIF / attached SAs; enforce `iam.disableServiceAccountKeyCreation` at folder/org; introduce custom IAM roles; demote primitive grants on default SAs (R2).
- **F3. Foundation Terraform.** Stand up the `bootstrap/` + `foundation/` + `governance/` modules; CI via WIF (no keys); policy gate (`gcloud beta terraform vet` + OPA); state buckets per env with CMEK.
- **F4. Observability backbone.** `observability/` module: Slack notification channel (token in Secret Manager), alert policies, log sinks → BigQuery audit dataset, log-based metrics for the policy/audit/error rate path, baseline dashboards, uptime checks on the Slack-notifier and Action Broker (R3).
- **F5. Security baseline.** Enable Security Command Center v2 at folder; Model Armor floor settings (`INSPECT_AND_BLOCK`); custom SCC module for SA-key-creation alerting; replace any auto-mode `default` VPC with a custom-mode VPC; close any internet-open SSH/RDP rules; align CMEK across environments (R4).
- **F6. Eventing spine.** `eventing/` module: Pub/Sub topics + schemas (`ops.signals`, `ops.findings`, `ops.actions.*`, `ops.audit`, `ops.notifications`) + DLQs; Eventarc for SCC findings, Monitoring alerts, Audit Logs.
- **F7. Slack-notifier service.** Cloud Run service rendering `OpsNotification` → Block Kit; secrets via Secret Manager; Slack interactivity endpoint (no agent yet — used immediately by Cloud Monitoring native channel).
- **F8. Action Broker service (skeleton, no live agent traffic yet).** Cloud Run service exposing the `propose / request_approval / execute / rollback` MCP tools; policy engine wired; idempotency store; *not yet exercised by an agent* — exercised by a manual smoke test.
- **F9. Standardise residency.** Default-region policy to `europe-west2`; migrate stragglers; document residency exceptions (R6).
- **F10. Pilot the SRE Agent in Tier 0/1 observe-only mode.** Single ADK 2.0 Python agent on Agent Engine; consumes Logging/Monitoring/Trace MCP; emits Findings to Slack via the Slack-notifier; no actions. Runs against `dev` only.

**Exit criteria for Phase 1:**

- Zero exported SA keys (verified by an SCC custom module).
- ≥10 Cloud Monitoring alert policies in place with Slack delivery.
- Audit BQ dataset receiving > 0 rows/day from log sinks.
- SRE agent producing ≥1 Finding per signal in `dev`, MTTR-to-recommendation < 5 min.
- Terraform apply requires WIF; no human can apply from a laptop.

### Phase 2 — The Roster (months 3–9)

*Goal: the full agent roster, with bounded action authority, an operational autonomy ladder, and a hardened control plane.*

**Deliverables:**

- **R-1. Deploy DevSecOps, Platform, and FinOps agents** at Tier 0/1 in `dev`; promote SRE Agent to Tier 2 for the safest action classes (`cloud_run.scale_within_range`, `cloud_run.rollback_to_previous` in `dev`) under the action-class catalogue (§3.3).
- **R-2. Action Broker for real.** First production-shaped action: a `dev`-only `cloud_run.rollback_to_previous` and an SA-key-deletion remediation. Two-approver Tier-3 wired in.
- **R-3. Custom MCP servers.** Runbook & Knowledge MCP; Org Context MCP. Both Cloud Run, behind IAM and Model Armor analogue (own input hygiene).
- **R-4. A2A wiring.** Orchestrator routes by skill match; the SRE Agent can call the Platform agent for "was there a deploy?" out-of-loop.
- **R-5. CI eval gate.** Gen AI Evaluation Service (Preview) trajectory evaluations in CI on every agent change; nightly online eval on 1% sampled prod traffic; eval-score regression as a hard PR gate.
- **R-6. Memory Bank for the Orchestrator** (incident lore — past incidents, common false-positives) — production-aware, with revisions when GA.
- **R-7. VPC-SC perimeter — dry-run.** Stand up a `_dry_run_*` perimeter around the `ops-agents-prod` project + the audit BQ dataset; iterate until clean; do **not** enforce yet.
- **R-8. Cloud Assist Investigations integration** (subject to Premium Support entitlement — R13). Via the Cloud Assist MCP server, not via an unverified REST surface.
- **R-9. Promote action classes** through the policy-PR ritual: dev Tier 2 → prod Tier 2; introduce prod Tier 3 for `cloud_run.rollback_to_previous`.
- **R-10. SCC v2 + Agent Security dashboard** (Announced-GA*) — verify in-console and enable when actually GA; otherwise fall back to log-based custom modules.
- **R-11. FinOps automation.** Wrap the Cloud Assist FinOps agent (Announced-GA*) and the platform's billing-export queries; daily anomaly digest in `#ops-finops`.

**Exit criteria for Phase 2:**

- All five agents live in `prod` at ≥ Tier 1.
- At least three Tier-2 action classes in `prod`, with > 95% post-condition success rate and < 5% rollback rate.
- Eval trajectory CI gate blocking at least one regression per quarter.
- Two-approver Tier-3 workflow exercised at least monthly.

### Phase 3 — Bounded Autonomy & UX (months 9–18+)

*Goal: progressive autonomy under tight bounds; vendor and external agents via A2A; operator UX through Gemini Enterprise; continuous-learning loop.*

**Deliverables:**

- **A-1. Enforce VPC-SC** (dry-run → enforced) around the agent control plane and audit dataset.
- **A-2. Adopt Agent Identity (Preview → GA)** behind feature flag; cert-bound tokens replace SA tokens for production agents.
- **A-3. Tier 3/4 expansion** to additional action classes (e.g., `gke.cordon_drain_node`, `terraform.apply` for declared-safe-diff plans), each through the policy promotion ritual.
- **A-4. Gemini Enterprise gallery surface** — expose the Ops Orchestrator as a Gemini Enterprise agent, with app-level IAM and audit logs, so non-engineers can converse with the duty manager (status reports, incident lookups). Optional and additive.
- **A-5. External / vendor agents via A2A** — e.g., a third-party FinOps optimiser; an outsourced SOC's TIN; an enterprise change-management agent. Each registered behind the Agent Registry and skill-matched by the Orchestrator.
- **A-6. Continuous-learning loop.** Audit ledger → Memory Bank curation pipeline → Gen AI Evaluation Service dataset → next agent training/eval cycle.
- **A-7. Drift-prevention agents** — Platform Agent shifts from drift *detection* to drift *prevention* by gating CI on declared-state divergence.
- **A-8. Multi-region resilience** — failover topology if scope grows beyond a single primary region.

There is **no Phase 4**: the design is intentionally indefinite at horizon 3 — by then, the Google capability set will have moved on, and the architecture (model-agnostic, tool-agnostic, agent-agnostic via A2A) is constructed to absorb that movement without re-platforming.

---

## Part 10 — Prioritised Recommendations

The recommendations below collapse the design into a numbered, sequenced backlog. Each is independently actionable. Priorities are: **P0** (do first / blocker), **P1** (do early), **P2** (do during Phase 2), **P3** (Phase 3+).

| # | Recommendation | Priority | Rationale | Dependencies | Risks if not done |
|---|---|---|---|---|---|
| **R1** | Establish a **Cloud Identity / Organisation** resource and a folder hierarchy; migrate the four existing projects in. | **P0** | Without an Organisation, no policy inheritance, no org-scoped SCC, no centralised IAM, no break-glass — every later control is weaker. | A free-tier Cloud Identity sign-up; no other GCP prerequisites. | All later governance work is structurally compromised. |
| **R2** | **Eliminate any exported service-account keys** and enforce `iam.disableServiceAccountKeyCreation`; standardise on attached SAs + WIF for CI; replace any key-based SAs with WIF identities. | **P0** | Long-lived bearer credentials are exfiltratable and disproportionately dangerous on agent platforms where many SAs hold narrow write grants. | R1 (for folder-level org policy); a small WIF-pool Terraform module. | Trivially exploitable credential exposure; any later identity model rests on insecure ground. |
| **R3** | Stand up the **observability backbone**: native Slack `notification_channel` (using the existing `slack-token`), ≥10 baseline alert policies, log sinks → BQ audit dataset, log-based metrics for error rate / policy denials / token spend, baseline dashboards, uptime checks. | **P0** | The estate currently has **zero alerts and no log routing**; agents cannot operate where nothing is observable, and the operator cannot operate the agents. | R1 (folder sinks). | No visibility; agents cannot be operated safely; SLA-bound work is impossible. |
| **R4** | Enable **Security Command Center v2** at folder; configure **Model Armor floor settings** (`INSPECT_AND_BLOCK`) and starter templates; install a **custom SCC module** that alerts on SA-key creation. | **P0** | DevSecOps agent has no findings source without SCC; Model Armor is the AI-safety control already API-enabled but inert; SA-key alerting catches regressions of R2. | R1; R2 to demonstrate effectiveness. | DevSecOps agent has no input; AI-safety control remains unused; key sprawl recurs silently. |
| **R5** | Adopt the **Terraform foundation repo** (this scaffold); pin `google` 7.x and `google-beta` 7.x exactly per env; GCS backend per env with CMEK and native locking; CI via WIF; policy gate (`gcloud beta terraform vet` + OPA); no `terraform apply` from laptops. | **P0** | The common alternative — over-privileged service-account-key-based IaC — fails closed only if the runner is uncompromised; a governed platform should not depend on that assumption. | R2 (WIF). | Continued ad-hoc IaC; supply-chain of the platform-as-code is the next finding. |
| **R6** | **Standardise residency** on `europe-west2` (London) for the UK-based owner; document an exception list; align CMEK, BQ datasets, Workflows, Firestore to the standard. | **P1** | Today's residency is mixed (`europe-west2`, `us-central1`, `nam5`) with no policy; for a UK owner and GBP billing this is a compliance hygiene issue. | R1 (for `gcp.resourceLocations` org policy). | Compliance ambiguity; future regulatory work re-opens the platform. |
| **R7** | Build the **Action Broker** as the only execution surface for agent writes, with per-action-class impersonation, idempotency, post-condition verification and auto-rollback. | **P1** | The architectural choke-point that makes action-taking agents defensible; nothing in the design depends on every agent being well-behaved. | R2, R5; an `eventing/` Pub/Sub spine. | Distributed write IAM across agents; blast radius of any prompt injection vastly larger. |
| **R8** | Deploy the **Slack-notifier service** rendering the `OpsNotification` contract (Part 6.6) — *before* any agent exists; have Cloud Monitoring's native channel use the same Slack workspace immediately. | **P1** | Slack discipline must be in place before agents start posting; investment is reused by R3 alerts on day one. | R3; existing `slack-token` secret. | Inconsistent / noisy / unsafe Slack messaging; "approval fatigue" pre-built. |
| **R9** | Deploy the **Orchestrator + SRE Agent** in `dev` first, **Tier 0/1 only** (observe + recommend, no execute), as the pilot. | **P1** | Earn the right to act by demonstrating the right to recommend; pilot validates the eventing/MCP/Slack path end-to-end. | R3, R5, R7, R8. | Premature autonomy; bad first impressions; reputational drag. |
| **R10** | Codify the **autonomy ladder** (Tier 0 → 4) as policy-as-code with the **promotion ritual** (§5.7); set Tier 1 as the default for every new action class. | **P1** | Prevents implicit tier creep; makes "more autonomy" an explicit, reviewable decision. | R5, R7. | Quiet drift to over-autonomy; "we already do X" arguments. |
| **R11** | Adopt **Gen AI Evaluation Service** (Preview) **trajectory metrics** as the agent CI regression gate, and run **online eval** on 1% sampled prod traffic. | **P2** | Catches behavioural regressions that unit tests miss; the documented way to keep an agent's reasoning honest over time. | R9; sample data in the audit ledger. | Silent behavioural drift; the "well, last week it worked" failure mode. |
| **R12** | **Pilot Agent Identity (Preview)** for non-prod agents behind a feature flag; keep dedicated service accounts as the GA fallback for prod. | **P2** | The structurally correct identity model for autonomous agents; pilot reduces migration risk when GA. | R2. | A larger migration later if Preview becomes the only supported path. |
| **R13** | Confirm **Premium Support eligibility** and request access to **Cloud Assist Investigations** (Preview, access-gated since 10 Apr 2026); integrate via the **Cloud Assist MCP server**, not via an unverified REST surface. | **P2** | The named RCA agent is a meaningful capability lift for the SRE agent; access gating means timing matters. | Commercial decision; Cloud Assist MCP server availability. | Either reinvent the RCA capability or live without it. |
| **R14** | Stand up a **VPC Service Controls** perimeter (dry-run first, then enforced) around the `ops-agents-prod` project and the audit BQ dataset. | **P2** | A hard data-exfiltration boundary; the additional control when Tier-3+ actions are common. | R1; R5; understanding of Agent Engine perimeter caveat (max-instances cap). | Data-exfiltration risk remains entirely on IAM, with no network backstop. |
| **R15** | Establish a **quarterly governance review** (auditor-led) over the audit ledger; require tier-promotion proposals be substantiated from the ledger; produce an annual platform report. | **P2** | Closes the loop — without an external review, autonomy ratchets only one way. | R3 (audit data exists). | "Audit theatre"; promotions without evidence. |
| **R16** | When Google **Agent Registry MCP** and the **SCC Agent Security dashboard** transition from Announced-GA* to actually GA in-console, **adopt them** and **retire the local Firestore catalogue and custom SCC modules** that backfilled them. | **P3** | Future-readiness; reduces custom code as the native surface matures. | Native GA. | Maintaining bespoke equivalents indefinitely. |

### Headline risks (consolidated)

| Risk | Severity | Mitigation |
|---|---|---|
| Acting before foundation is safe | **High** | Phase 1 is recommend-only; the autonomy ladder is policy-gated. |
| Over-trusting Announced-GA* features | **Medium–High** | Every Announced-GA* item has a GA fallback in the design; verify per-feature in-console before depending on it. |
| Prompt injection through poisoned telemetry | **High** | Model Armor floor + custom MCP input hygiene + structured-output schema + Broker validation. |
| Unbounded agent cost | **Medium** | Per-agent token budgets with hard caps; circuit breaker at 100%. |
| Approval fatigue | **Medium** | Channel discipline; one or two recommendations max per message; auto-expiry; two-approver rotation. |
| Single human principal | **Medium** | Phase 1 introduces named roles even if one human; immediate next hire claims the Approver role. |
| Cloud Assist Investigations access-gating | **Low** | Premium Support decision is explicit (R13); platform works without it. |
| Memory Bank cost / drift | **Low–Medium** | Memory treated as cache; Revisions adopted at GA. |

---

## Appendix A — Current-state evidence summary

*Omitted from this public reference (see Part 1 note).*

---

## Appendix B — Terraform resource coverage matrix

| Component / capability | Terraform resource(s) | Provider | Tag |
|---|---|---|---|
| Agent Engine reasoning engine | `google_vertex_ai_reasoning_engine` (+ `_iam_*`) | `google` | **GA** |
| Agent Engine Memory Bank (`context_spec`) | (sub-field of above) | `google-beta` | beta-only |
| Vertex AI endpoints / Model Garden deployment | `google_vertex_ai_endpoint`, `_endpoint_with_model_garden_deployment`, `_deployment_resource_pool` (+ `_iam_*`) | `google` | **GA** |
| Vertex AI vector search / RAG | `google_vertex_ai_index`, `_index_endpoint`, `_index_endpoint_deployed_index`, `_rag_engine_config` | `google` | **GA** |
| Discovery Engine (Agent Builder backbone) | 16 `google_discovery_engine_*` resources | `google` | **GA** |
| Dialogflow CX (if used) | 15 `google_dialogflow_cx_*` resources | `google` | **GA** |
| Cloud Run v2 | `google_cloud_run_v2_service`, `_job`, `_worker_pool` (+ `_iam_*`) | `google` | **GA** |
| Cloud Functions 2nd gen | `google_cloudfunctions2_function` (+ `_iam_*`) | `google` | **GA** |
| Eventarc | `google_eventarc_trigger`, `_channel`, `_enrollment`, `_message_bus`, `_pipeline`, `_google_api_source`, `_google_channel_config` | `google` | **GA** |
| Pub/Sub | `google_pubsub_topic`, `_subscription`, `_schema` (+ `_iam_*`) | `google` | **GA** |
| Cloud Workflows | `google_workflows_workflow` | `google` | **GA** |
| Cloud Scheduler | `google_cloud_scheduler_job` | `google` | **GA** |
| Secret Manager | `google_secret_manager_secret`, `_secret_version` (+ regional + `_iam_*`) | `google` | **GA** |
| Service accounts + IAM | `google_service_account`, `_iam_member`/_binding/_policy, custom roles, ephemeral tokens | `google` | **GA** |
| Artifact Registry + Binary Authorization | `google_artifact_registry_repository`, `_rule`, `_vpcsc_config`, BinAuthz policy | `google` | **GA** |
| Cloud Monitoring | `google_monitoring_dashboard`, `_alert_policy`, `_notification_channel`, `_slo`, `_service`, `_uptime_check_config`, `_metric_descriptor`, `_group` | `google` | **GA** |
| Native Slack channel | `google_monitoring_notification_channel { type = "slack" }` with `sensitive_labels.auth_token_wo` | `google` | **GA** |
| Logging | `google_logging_project_sink`, `_metric`, `_log_scope`, `_log_view`, `_linked_dataset`, `_saved_query` | `google` | **GA** |
| Model Armor | `google_model_armor_template`, `google_model_armor_floorsetting` | `google` | **GA** |
| Security Command Center v2 | `google_scc_v2_*` (source, mute_config, notification_config, big_query_export at org/folder/project) | `google` | **GA** |
| VPC Service Controls | `google_access_context_manager_*` (incl. `_dry_run_*`) | `google` | **GA** |
| Org Policy | `google_org_policy_policy`, `google_org_policy_custom_constraint` | `google` | **GA** |
| CFT modules (consumed) | `terraform-google-modules/project-factory` 18.2.0, `…/network` 18.1.0, `…/iam`, `…/log-export`, `…/org-policy`, `…/vpc-service-controls`, `GoogleCloudPlatform/cloud-run` 0.32.0 | registry | **GA** (cloud-run module is 0.32.0, pre-1.0 — pin exactly) |
| Gemini Enterprise app surface (gallery, Agent Designer) | — | — | **No Terraform surface** — Console/API only |
| Cloud Assist Investigations | — | — | **No public Terraform surface** today; integrate via Cloud Assist MCP |
| Agent Registry (resources) | (sparse today; `agentregistry.googleapis.com` API enabled) | — | **Partial / verify** — wrap via own Firestore catalogue until GA |
| Agent Identity (SPIFFE) | (in-progress provider coverage) | `google` / `google-beta` | **Preview** — use dedicated SAs as GA fallback |

---

## Appendix C — `OpsNotification v1` JSON Schema (excerpt)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
$id:     "https://schemas.example.org/ops/notification/v1.json"
title:   "OpsNotification"
type:    object
required:
  - schema
  - notification_id
  - correlation_id
  - produced_at
  - severity
  - environment
  - domain
  - summary
  - affected_component
  - impact
  - recommended_actions
  - human_required
  - references
  - agent
properties:
  schema:           { const: "ops.notification.v1" }
  notification_id:  { type: string, pattern: "^ntf_[0-9TZ:\\-]+_[a-z0-9]{6,}$" }
  correlation_id:   { type: string }
  produced_at:      { type: string, format: date-time }
  severity:         { enum: [info, low, medium, high, critical] }
  environment:      { enum: [dev, prod] }
  domain:           { enum: [sre, devsecops, platform, finops, orchestrator] }
  summary:
    type: string
    minLength: 20
    maxLength: 400
    description: Plain-English summary of the issue; no JSON, no raw log lines.
  affected_component:
    type: object
    required: [type, name, project]
    properties:
      type:    { type: string }              # cloud_run_service | gke_cluster | iam_principal | ...
      name:    { type: string }
      project: { type: string }
      region:  { type: string, nullable: true }
  impact:           { type: string, minLength: 20 }
  likely_cause:     { type: string, nullable: true }
  recommended_actions:
    type: array
    minItems: 1
    items:
      type: object
      required: [id, label, action_class, tier, reversible]
      properties:
        id:                  { type: string }
        label:               { type: string }
        action_class:        { type: string }       # from policy action-class catalogue
        tier:                { type: integer, minimum: 0, maximum: 4 }
        estimated_duration_s:{ type: integer }
        reversible:          { type: boolean }
  human_required:   { type: boolean }
  approval_window_until: { type: string, format: date-time, nullable: true }
  references:
    type: object
    properties:
      logs:      { type: string, format: uri, nullable: true }
      dashboard: { type: string, format: uri, nullable: true }
      trace:     { type: string, format: uri, nullable: true }
      runbook:   { type: string, format: uri, nullable: true }
      scc:       { type: string, format: uri, nullable: true }
      ticket:    { type: string, format: uri, nullable: true }
      workflow:  { type: string, format: uri, nullable: true }
  agent:
    type: object
    required: [identity, model]
    properties:
      identity: { type: string }       # spiffe://... or SA email
      model:    { type: string }       # e.g., gemini-3-pro
      tokens:
        type: object
        properties:
          in:  { type: integer }
          out: { type: integer }
      trace_id: { type: string, nullable: true }
```

The schema is published to a `schemas/` bucket and **referenced by Pub/Sub** (`google_pubsub_schema`); the topic enforces schema-validation at publish time.

---

## Appendix D — Glossary and references

**Glossary**

- **A2A** — Agent2Agent Protocol; open Linux-Foundation-hosted standard for agent-to-agent communication.
- **ADK** — Agent Development Kit; Google's open-source toolkit for building agents (Python/Java/Go/TypeScript). v2.0 (Python) GA 2026-05-19.
- **Agent Engine** — Vertex AI's managed agent runtime ("Deployments" in the post-Next-'26 naming); Terraform: `google_vertex_ai_reasoning_engine`.
- **Agent Identity** — SPIFFE-based cryptographic agent identity (Preview); supersedes SA-based identity for agents over time.
- **Cloud Assist** — GCP-native operations assistant (Gemini Cloud Assist), now agentic; includes FinOps and Infra-Ops agents and **Investigations** (Preview, access-gated).
- **Gemini Enterprise** — the governed, end-user agent app/workspace (the former Agentspace).
- **Gemini Enterprise Agent Platform** — the rebranded Vertex AI / Agent Builder family (developer/runtime plane).
- **MCP** — Model Context Protocol; the standard for agent-to-tool calls. Google operates a managed remote MCP fleet.
- **PAB** — Principal Access Boundary; an IAM mechanism that caps the resource set a principal can ever reach, independent of role grants.
- **SCC / SCC v2** — Security Command Center; v2 resource family in the Terraform provider is the recommended target.
- **TIN** — Triage & Investigation Agent (Google Security Operations).

**Primary references** (the load-bearing sources for this review)

- Google Cloud Next '26 Wrap-Up (Apr 25, 2026): https://cloud.google.com/blog/topics/google-cloud-next/google-cloud-next-2026-wrap-up
- Gemini Cloud Assist at Next '26: https://cloud.google.com/blog/products/application-development/gemini-cloud-assist-at-next26
- The new Gemini Enterprise: one platform for agent development: https://cloud.google.com/blog/products/ai-machine-learning/the-new-gemini-enterprise-one-platform-for-agent-development
- Google-managed MCP servers are available for everyone (Apr 29, 2026): https://cloud.google.com/blog/products/ai-machine-learning/google-managed-mcp-servers-are-available-for-everyone
- MCP Supported Products: https://docs.cloud.google.com/mcp/supported-products
- Vertex AI Agent Engine overview: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview
- ADK release notes / ADK 2.0: https://adk.dev/release-notes/ ; https://adk.dev/2.0/
- A2A protocol — Linux Foundation press, 1-year update: https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year
- Cloud Assist Investigations: https://docs.cloud.google.com/cloud-assist/investigations
- SecOps Triage & Investigation Agent: https://docs.cloud.google.com/chronicle/docs/secops/triage-investigation-agent
- Agent Identity overview: https://docs.cloud.google.com/iam/docs/agent-identity-overview
- Model Armor + Google Cloud MCP integration: https://docs.cloud.google.com/model-armor/model-armor-mcp-google-cloud-integration
- Gen AI Evaluation Service — agent evaluation: https://cloud.google.com/blog/products/ai-machine-learning/introducing-agent-evaluation-in-vertex-ai-gen-ai-evaluation-service
- Pub/Sub, Webhook, and Slack notifications are GA: https://cloud.google.com/blog/products/operations/pub-sub-webook-and-slack-notifications-are-now-available
- HashiCorp Terraform Registry — `hashicorp/google` 7.33.0 (live provider-schema queries): https://registry.terraform.io/providers/hashicorp/google/latest
- `google_vertex_ai_reasoning_engine` docs: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/vertex_ai_reasoning_engine
- `google_monitoring_notification_channel` docs (Slack channel example): https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_notification_channel
- Best practices for root modules / reusable modules (Google's Terraform guidance): https://docs.cloud.google.com/docs/terraform/best-practices/root-modules
- Recommended AI Controls framework: https://cloud.google.com/blog/products/identity-security/audit-smarter-introducing-our-recommended-ai-controls-framework

— *End of review* —
