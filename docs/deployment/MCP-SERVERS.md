# Google Cloud MCP servers for the AOP agents

How the AOP agents consume Google Cloud's managed [MCP servers](https://docs.cloud.google.com/mcp/overview)
for observability, diagnostics, root-cause analysis, and resource inspection —
**read-only by default, least-privilege, with all writes routed through the
Action Broker.**

## Model

- **Clients = the AOP agents.** Each agent (orchestrator, SRE, DevSecOps,
  Platform, FinOps) runs as its own service account / Vertex AI **Agent
  Identity** and connects to the managed remote MCP endpoints
  (`https://<service>.googleapis.com/mcp`, Streamable HTTP, Bearer token from the
  agent's ADC). Wiring: [`agents/aop_common/mcp_tools.py`](../../agents/aop_common/mcp_tools.py).
- **Read-only by construction.** An agent SA holds `roles/mcp.toolUser` (permits
  _invoking_ the MCP tool surface) plus only **viewer** product roles. Even if a
  server exposes a write tool, IAM denies it.
- **Decision/execution separation.** Agents _decide_; only the **Action Broker**
  _writes_. No agent has a write/admin role; remediation is proposed to the
  broker, which executes under its approval tiers (HITL for Tier 3/4).

## Enabled servers (purpose-fit, read-only)

| Server                            | Endpoint                                 | Purpose                            | Permitted actions                          | Backing API                          | Required role                                                  |
| --------------------------------- | ---------------------------------------- | ---------------------------------- | ------------------------------------------ | ------------------------------------ | -------------------------------------------------------------- |
| Cloud Logging                     | `logging.googleapis.com/mcp`             | Read logs for diagnostics / RCA    | read-only (list/query entries)             | `logging.googleapis.com`             | `roles/logging.viewer` (DevSecOps: `logging.privateLogViewer`) |
| Cloud Monitoring                  | `monitoring.googleapis.com/mcp`          | Read metrics, alerts, uptime, SLOs | read-only (query time series)              | `monitoring.googleapis.com`          | `roles/monitoring.viewer`                                      |
| Cloud Trace                       | `cloudtrace.googleapis.com/mcp`          | Latency / span RCA                 | read-only (read traces)                    | `cloudtrace.googleapis.com`          | `roles/cloudtrace.user` (read)                                 |
| Error Reporting                   | `clouderrorreporting.googleapis.com/mcp` | Service error triage               | read-only (list error groups)              | `clouderrorreporting.googleapis.com` | `roles/errorreporting.viewer`                                  |
| Cloud Run                         | `run.googleapis.com/mcp`                 | Inspect services/revisions         | **read-only** (describe/list)              | `run.googleapis.com`                 | `roles/run.viewer`                                             |
| Cloud Asset Inventory _(Preview)_ | `cloudasset.googleapis.com/mcp`          | Resource inventory / drift / RCA   | read-only (search/list/history)            | `cloudasset.googleapis.com`          | `roles/cloudasset.viewer`                                      |
| Network Intelligence Center       | `networkmanagement.googleapis.com/mcp`   | Connectivity/network diagnostics   | read-only diagnostics (connectivity tests) | `networkmanagement.googleapis.com`   | `roles/networkmanagement.viewer`                               |

**Expected inputs/outputs (all servers):** input = a scoped query (log filter,
metric type + window, trace/asset filter, service name, connectivity-test
params); output = structured read data (log entries, time series, spans, error
groups, asset records, reachability results). No input mutates state.

## Per-agent allow-lists (least-privilege)

| Agent            | MCP servers                                                                  | Viewer roles granted (besides `roles/mcp.toolUser`)                                                                         |
| ---------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Orchestrator** | Logging, Monitoring                                                          | `logging.viewer`, `monitoring.viewer`                                                                                       |
| **SRE**          | Logging, Monitoring, Trace, Error Reporting, Cloud Run, Network Intelligence | `logging.viewer`, `monitoring.viewer`, `cloudtrace.user`, `errorreporting.viewer`, `run.viewer`, `networkmanagement.viewer` |
| **DevSecOps**    | Logging, Monitoring, Asset Inventory                                         | `logging.privateLogViewer`, `monitoring.viewer`, `cloudasset.viewer`                                                        |
| **Platform**     | Logging, Monitoring, Asset Inventory, Cloud Run                              | `logging.viewer`, `monitoring.viewer`, `cloudasset.viewer`, `run.viewer`                                                    |
| **FinOps**       | Monitoring                                                                   | `monitoring.viewer` (+ BigQuery billing — deferred, see below)                                                              |

All five also receive `roles/mcp.toolUser`.

## Safety boundaries & when human approval is required

- **Default = read-only.** Enforced two ways: viewer-only IAM, and the
  `gcloud beta services mcp content-security` "prevent read-write MCP tool use"
  control + Model Armor screening of MCP calls/responses.
- **No direct remediation via MCP.** Cloud Run remediation (scale-within-range,
  rollback-to-previous, restart-revision) is **not** performed through the Cloud
  Run MCP server. An agent _proposes_ the action to the **Action Broker**
  (`propose_action`); the broker evaluates policy and executes it under its
  tiered model:
  - **Tier 0–2** (recommend / low-risk): broker may execute per policy.
  - **Tier 3–4** (impactful/irreversible): **human approval required** via the
    Slack interactivity flow before execution.
- **No agent holds** `roles/owner|editor`, any `*.admin`, write, or
  `iam.*` mutate roles. Secret Manager / IAM / Artifact Registry have **no** MCP
  server and are not exposed.

## Enablement (reproducible, auditable)

1. **APIs** — enabled in Terraform (`modules/foundation` `required_apis`):
   `cloudtrace`, `clouderrorreporting`, `cloudasset`, `networkmanagement` (the
   rest were already enabled). Reproducible + destroyable.
2. **IAM** — `roles/mcp.toolUser` + the viewer roles above are granted in
   Terraform: `modules/agent-runtime` (the dev/prod path, fully wired) and
   `modules/agents/_base` (the framework path grants `mcp.toolUser`; per-agent
   wrappers must include the viewer roles from the matrix in their
   `project_iam_roles`).
3. **Read-only enforcement (one-off, documented in `GCLOUD-COMMANDS.md`):**
   ```bash
   gcloud beta services mcp content-security add --project=PROJECT_ID \
     --prevent-read-write   # confirm exact flag against `gcloud beta services mcp content-security --help`
   ```
   Reversal: `gcloud beta services mcp content-security remove …`.
4. **Client wiring** — `agents/aop_common/mcp_tools.py` per-agent allow-lists.

## Auditability

- **Cloud Audit Logs** record MCP tool use (who/what/when), attributed to the
  agent SA / Agent Identity.
- **Cloud Trace** can monitor MCP tool latency/usage.
- All configuration is in Git (Terraform + `mcp_tools.py` + this doc).

## Excluded / deferred (and why)

| Item                                                                      | Why                                                                                                                                                                 |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GKE, Compute Engine                                                       | not in the AOP stack (Cloud Run only)                                                                                                                               |
| Resource Manager MCP                                                      | overlaps Cloud Asset Inventory for inspection                                                                                                                       |
| SecOps / Chronicle                                                        | not used here (SCC findings flow via the governance pipeline)                                                                                                       |
| Gemini Cloud Assist, Developer Knowledge, Agent Registry, Recommender MCP | Preview / unverified as supported servers; avoid broad/ambiguous surface                                                                                            |
| **BigQuery MCP**                                                          | **deferred** — _FinOps billing-BigQuery (read-only) is the first planned addition_; would grant FinOps `bigquery.dataViewer`/`jobUser` scoped to the billing export |
| Pub/Sub MCP                                                               | deferred — eventing is consumed directly, not via MCP, for now                                                                                                      |
| Broad `@google-cloud/gcloud-mcp`                                          | wraps the whole gcloud CLI (too broad); scoped per-product servers are the least-privilege path                                                                     |

## Caveats

- Google Cloud MCP is **beta** (`gcloud beta …`); Cloud Asset Inventory MCP is
  **Preview**. Re-confirm endpoint availability and the exact `content-security`
  flags against the [official docs](https://docs.cloud.google.com/mcp/supported-products).
- **The agent tier is not deployed** (the ADK builders are stubs — see
  [`AGENT-DEPLOY.md`](./AGENT-DEPLOY.md)). This wiring is therefore _ready-to-use_:
  the APIs apply now; the `mcp.toolUser` + viewer IAM binds when the agent SAs
  are created at deploy.
- The ADK↔endpoint Bearer/ADC handshake in `build_mcp_toolsets()` should be
  validated against the installed `google-adk` version at first deploy.
