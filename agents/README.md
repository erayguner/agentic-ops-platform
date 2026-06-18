# AOP Agent Skeletons — ADK 2.0

Python agent skeletons for the Agentic Operations Platform. These are
**pattern demonstrations** — every ADK 2.0 / MCP / Pub/Sub call is wired
through abstractions that are safe to run offline. The skeletons compile
cleanly without live infrastructure and produce no real side effects until
the `LIVE_*` env flags are set on the corresponding services.

> **Python packaging is managed by [uv](https://docs.astral.sh/uv/) — not pip.**

## Layout

```text
agents/
├── pyproject.toml          ← uv-managed; google-adk==2.1.*; hatchling build backend
├── uv.lock                 ← committed; regenerate with `uv lock`
├── README.md
├── aop_common/             ← shared library
│   ├── __init__.py
│   ├── config.py           ← AopSettings (Pydantic Settings, AOP_* env vars)
│   ├── schemas.py          ← all v1 schemas: OpsSignal, Finding, Recommendation,
│   │                         ActionRequest, ActionApproval, ActionExecuted,
│   │                         OpsNotification, AuditRecord
│   ├── mcp_tools.py        ← McpToolset wiring + per-agent allow-lists
│   ├── action_client.py    ← ActionBrokerClient — propose_action only
│   ├── policy_client.py    ← OrgContextClient — read-only lookups
│   ├── slack_emitter.py    ← SlackEmitter → ops.notifications
│   ├── audit.py            ← AuditEmitter → ops.audit
│   └── models.py           ← ModelFactory with fallback list
├── aop_orchestrator/       ← ADK 2.0 WorkflowAgent (graph + HITL)
│   ├── agent.py
│   └── prompts.py
├── aop_sre/                ← LlmAgent → Finding output
├── aop_devsecops/
├── aop_platform/
├── aop_finops/
├── aop_decommission/       ← WorkflowAgent + pure-Python closure engine
│   ├── inventory.py        ← discover + reconcile + classify
│   ├── exemptions.py       ← policy-driven retention (fail-safe)
│   ├── planner.py          ← dry-run plan + dependency-ordered teardown
│   ├── executor.py         ← staged, idempotent, propose-only via the Broker
│   ├── validation.py       ← post-decommission assurance
│   ├── report.py           ← closure report (redacted)
│   └── campaign.py         ← end-to-end lifecycle
└── deployment/
    └── deploy.py           ← CLI skeleton — dry-run only
```

Each `aop_*` directory is a Python package; directory names match package
names exactly, so no source-to-target mapping is required in `pyproject.toml`.

## Agent roster

| Agent            | Package            | SA                | Mandate                                               |
| ---------------- | ------------------ | ----------------- | ----------------------------------------------------- |
| Ops Orchestrator | `aop_orchestrator` | `sa-orchestrator` | Duty manager; dedup; route; HITL                      |
| SRE              | `aop_sre`          | `sa-sre`          | Latency, error rate, SLO, deploys                     |
| DevSecOps        | `aop_devsecops`    | `sa-devsecops`    | SCC, IAM drift, key exposure                          |
| Platform         | `aop_platform`     | `sa-platform`     | Drift, IaC state, hygiene, compliance                 |
| FinOps           | `aop_finops`       | `sa-finops`       | Cost, rightsizing, budget                             |
| Decommission     | `aop_decommission` | `sa-decommission` | Project closure: inventory, teardown plan, validation |

## Set up the dev environment

Install uv (one time, per workstation):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux
# or
brew install uv
```

Sync this component's dependencies into a local venv:

```bash
cd agents
uv sync                  # creates .venv/, installs runtime + dev deps
```

Bump the lockfile after editing `pyproject.toml`:

```bash
uv lock                  # commits the new uv.lock alongside pyproject.toml
```

Add a dependency:

```bash
uv add <package>         # runtime
uv add --dev <package>   # dev-only
```

## Compile check (mandatory before merge)

```bash
cd agents
uv run python -m compileall -q .
```

Or, from the repo root, covering all Python:

```bash
uv run python -m compileall -q agents services
```

## Lint and type-check

```bash
# from repo root (shared config in /pyproject.toml)
uv run ruff check agents
uv run ruff format --check agents
uv run mypy agents
```

## Tests

```bash
uv run --directory agents pytest
```

## Deployment (dry-run skeleton)

```bash
uv run python deployment/deploy.py --agent orchestrator \
    --project ops-agents-prod --region europe-west2 --env prod
```

This prints `would deploy …` — the real deployment is the deployer's CI
step (see `terraform/modules/agent-runtime/`).

## Key design decisions

- **`google-adk==2.1.*` pinned exactly.** ADK 2.0 GA'd 2026-05-19 (a breaking
  change from 1.x); the project tracks the 2.1.x line. Do not float to 3.x
  without review.
- **Model id is configuration.** `AOP_MODEL_ID` env var; default
  `gemini-3-pro`. Never hard-coded.
- **No agent holds write IAM on GCP.** All writes go through the Action
  Broker MCP only.
- **Structured output fixed to `Finding`.** Every specialist returns
  `Finding v1` as defined in `aop_common/schemas.py`.
- **Pub/Sub is the event spine.** Schema field names match the
  Pydantic models in `aop_common/schemas.py` exactly.
- **Agent Identity (SPIFFE) when GA.** Today: dedicated SA + PAB
  (`AOP_AGENT_IDENTITY` env var; SPIFFE-shaped string accepted as a
  forward-compat placeholder).

## Environment variables

All configuration comes from env vars with prefix `AOP_`. See
`aop_common/config.py` for the full list. Required vars:

| Variable                         | Purpose                                |
| -------------------------------- | -------------------------------------- |
| `AOP_PROJECT`                    | Target GCP project                     |
| `AOP_AGENT_IDENTITY`             | SA email or SPIFFE ID                  |
| `AOP_ACTION_BROKER_MCP_ENDPOINT` | Cloud Run URL of the Action Broker     |
| `AOP_ORG_CONTEXT_MCP_ENDPOINT`   | Cloud Run URL of the Org Context MCP   |
| `AOP_MODEL_ID`                   | Default model id (e.g. `gemini-3-pro`) |
| `AOP_ENVIRONMENT`                | `dev` or `prod`                        |
