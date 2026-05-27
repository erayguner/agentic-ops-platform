# Agentic Operations Platform (AOP)

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](./LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3130/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](./.pre-commit-config.yaml)
[![Secret Scan](https://github.com/erayguner/agentic-ops-platform/actions/workflows/secret-scan.yml/badge.svg?branch=main)](https://github.com/erayguner/agentic-ops-platform/actions/workflows/secret-scan.yml)
[![CodeQL](https://github.com/erayguner/agentic-ops-platform/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/erayguner/agentic-ops-platform/actions/workflows/codeql.yml)
[![Trivy](https://github.com/erayguner/agentic-ops-platform/actions/workflows/trivy.yml/badge.svg?branch=main)](https://github.com/erayguner/agentic-ops-platform/actions/workflows/trivy.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/erayguner/agentic-ops-platform/badge)](https://scorecard.dev/viewer/?uri=github.com/erayguner/agentic-ops-platform)
[![Dependabot](https://img.shields.io/badge/dependabot-enabled-025E8C.svg?logo=dependabot&logoColor=white)](./.github/dependabot.yml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-FE5196.svg?logo=conventionalcommits&logoColor=white)](https://www.conventionalcommits.org/en/v1.0.0/)

A reference scaffold for a **governed multi-agent DevSecOps / SRE / Platform Engineering** framework on Google Cloud, built around **Gemini Enterprise Agent Platform** (the rebranded Vertex AI Agent Builder), **ADK 2.0**, **Agent2Agent (A2A)**, and the **Google-managed MCP server fleet**.

> This repo accompanies a strategic and technical design review prepared on **2026-05-22**.
> Status: **skeleton** — the load-bearing surface area is defined and validate-ready; executors and full agent logic are stubs.
> Conformance: **`AGENT_GOVERNANCE_FRAMEWORK v1.1`** — see [`docs/GOVERNANCE-MAPPING.md`](./docs/GOVERNANCE-MAPPING.md) for the per-control attestation.

---

## Read me in this order

1. **`docs/DESIGN-REVIEW.md`** — the complete strategic + technical design review (current state, capability landscape, target architecture, MCP strategy, governance, observability + Slack contract, Terraform approach, security/resilience/escalation, roadmap, prioritised recommendations, appendices).
2. **`docs/AGENT_GOVERNANCE_FRAMEWORK.md`** — the version-pinned governance framework this project conforms to (v1.1). Upstream-owned, downstream-adopted; do not edit in this repo (raise the change upstream and re-vendor).
3. **`docs/GOVERNANCE-MAPPING.md`** — the AOP-specific Appendix A: every framework control mapped to the file / module / resource that implements it here, plus the current §19 compliance attestation.
4. **`terraform/FRAMEWORK.md`** — the reusable Terraform deployment framework: per-agent modules, composition module, pre-flight script, examples for `dev` / `staging` / `prod` and downstream consumers, release-please integration, and rollback runbook.
5. **`terraform/`**, **`agents/`**, **`services/`** — the three scaffolds, each with its own `README.md`. Cross-component schemas are defined inline in `agents/aop_common/schemas.py`, `services/slack-notifier/schemas.py`, and `services/action-broker/schemas.py`.

---

## Layout

```text
agentic-ops-platform/
├── README.md                       ← you are here
├── docs/
│   └── DESIGN-REVIEW.md            ← the design review
├── terraform/
│   ├── bootstrap/                  ← one-time: state bucket, WIF, runner SA
│   ├── modules/
│   │   ├── foundation/             ← projects, baseline IAM, baseline VPC
│   │   ├── governance/             ← Org Policy, SCC v2, Model Armor
│   │   ├── eventing/               ← Pub/Sub spine + Eventarc
│   │   ├── observability/          ← dashboards, alerts, Slack channel, log sinks
│   │   ├── agent-runtime/          ← Vertex AI reasoning engines per agent
│   │   ├── action-broker/          ← Cloud Run for the Action Broker
│   │   └── slack-notifier/         ← Cloud Run for the Slack notifier
│   └── environments/{dev,prod}/    ← per-env root modules
├── agents/                         ← ADK 2.0 Python agent skeletons
│   ├── common/                     ← shared schemas, MCP wiring, Slack emitter, policy client
│   ├── orchestrator/               ← duty-manager agent (A2A hub)
│   ├── sre/
│   ├── devsecops/
│   ├── platform/
│   ├── finops/
│   └── deployment/                 ← deploys agents to Agent Engine
└── services/
    ├── slack-notifier/             ← Cloud Run; OpsNotification → Block Kit; interactivity webhook
    └── action-broker/              ← Cloud Run; custom MCP server; policy-gated execution
```

## Local development setup

Python package management uses **[uv](https://docs.astral.sh/uv/)** exclusively — not pip. Each Python component (`agents/`, `services/slack-notifier/`, `services/action-broker/`) is an independent uv project with its own `pyproject.toml` and `uv.lock`. Shared linter/type-checker/test config lives in the root `pyproject.toml`.

```bash
# One-time per workstation
curl -LsSf https://astral.sh/uv/install.sh | sh        # install uv
uv sync                                                # repo-wide dev tools
uv tool install pre-commit
uv run pre-commit install --install-hooks

# Per component
uv sync --directory agents
uv sync --directory services/slack-notifier
uv sync --directory services/action-broker

# Validate
uv run pre-commit run --all-files
terraform -chdir=terraform/environments/dev  validate
terraform -chdir=terraform/environments/prod validate
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full branching strategy, Conventional Commits convention, and PR process.

## Quick principles (the long form is in the design review)

- **Native-first.** Google-managed runtime, MCP fleet, observability, security.
- **Decision/execution separation.** Specialist agents decide; only the **Action Broker** writes.
- **Policy-driven autonomy.** Tier per action-class per environment; promotion is a PR.
- **Default-safe.** Default action: recommend. Default approval: required. Default on failure: deny / rollback.
- **Model-, tool-, agent-agnostic.** ADK abstracts the model; MCP abstracts tools; A2A abstracts other agents.

## Status caveats

- **Skeleton, not a working deployment.** Apply-readiness comes after you bind the bootstrap module to your environment variables (project IDs, billing account, the Slack workspace tokens) and after the per-action-class executors are wired to real APIs.
- **ADK 2.0** went GA 2026-05-19 — pin exactly (`google-adk==2.0.*`).
- **Some Google capabilities used here are Preview** (Agent Identity, Memory Bank Revisions, Gen AI Evaluation Service, Cloud Asset Inventory MCP, Agent Registry MCP). See the design review §2.10 for the maturity snapshot; the scaffold's seams already accept the GA fallback.
- **No exported service-account keys.** CI must use Workload Identity Federation.

## Configuration

- `terraform/environments/*/terraform.tfvars` and the `bootstrap/` variables hold **placeholder values only**. Bind your own project IDs, billing-account ID, Slack OAuth token, and WIF identity at deploy time via your CI's secret manager — **never commit real values.** `*.auto.tfvars` and `*.local.tfvars` are gitignored for local overrides.
- Scaffold defaults are `LIVE_MODE=false` and `LIVE_SLACK_ENABLED=false` — services log rendered payloads instead of calling Google or Slack APIs.

## License & contributing

[MIT](./LICENSE) © 2026 Agentic Operations Platform contributors. See [`SECURITY.md`](./SECURITY.md) for vulnerability reporting and [`CONTRIBUTING.md`](./CONTRIBUTING.md) for contribution guidelines.
