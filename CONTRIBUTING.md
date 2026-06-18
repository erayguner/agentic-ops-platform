# Contributing

Thanks for your interest in improving the Agentic Operations Platform (AOP) reference scaffold.

## Quick reference

```bash
# One-time per workstation
curl -LsSf https://astral.sh/uv/install.sh | sh        # install uv
uv sync                                                # install repo dev tools
uv tool install pre-commit                             # install pre-commit globally
uv run pre-commit install --install-hooks              # wire hooks into this clone

# Per component (independent uv projects)
uv sync --directory agents
uv sync --directory services/slack-notifier
uv sync --directory services/action-broker

# Before pushing
uv run pre-commit run --all-files
terraform -chdir=terraform/environments/dev  validate
terraform -chdir=terraform/environments/prod validate
uv run pytest        # if tests exist for the area you touched
```

## Before you start

1. **Read** `docs/DESIGN-REVIEW.md`. The design review is the source of truth. Cross-component schemas are inline in the Python `schemas.py` modules (one each in `agents/aop_common/`, `services/slack-notifier/`, `services/action-broker/`) — these are the authoritative naming + field contracts. Any change that contradicts the design review or breaks a schema must justify it in the PR description and update the relevant files atomically in the same PR.
2. **Read** `docs/AGENT_GOVERNANCE_FRAMEWORK.md` and `docs/GOVERNANCE-MAPPING.md`. The framework is the governance standard this project conforms to (**v1.1**); the mapping is the per-control attestation. Any change to a control surface (`services/action-broker/policy/`, `aop_common/`, `terraform/modules/governance/`, approval/audit flows) **must** update `docs/GOVERNANCE-MAPPING.md` in the same PR. Framework changes go upstream — do not edit `docs/AGENT_GOVERNANCE_FRAMEWORK.md` in this repo.
3. **No secrets in commits.** Use `terraform.tfvars` for placeholder values only. Commit nothing that resembles a real GCP project ID, project number, billing-account ID, OAuth token, API key, SA key, or KMS key path. The `.gitignore` excludes `*.auto.tfvars` / `*.local.tfvars` — use those for any real values during local testing. **Gitleaks runs as a pre-commit hook as a last line of defence.**

## Source control

### Default branch

The default branch is `main`. It is protected:

- Linear history (no merge commits on `main`).
- No force-pushes.
- Required PR review (see "Pull-request process" below).
- Required passing CI checks.

### Branching strategy

This project follows **trunk-based development with short-lived feature branches**.

- Cut every change as a branch off `main`.
- Keep branches **short-lived** (target < 3 days). Rebase or pull `main` frequently; do not let a branch drift.
- Open a **draft PR early** to share work-in-progress and get CI feedback.
- **Squash-merge** to `main` when ready. The squash commit message becomes the canonical history entry and must follow Conventional Commits.

### Branch naming

```
<type>/<short-kebab-description>
```

`<type>` matches the Conventional Commits type set:

| Prefix      | Use for                                  |
| ----------- | ---------------------------------------- |
| `feat/`     | New capability                           |
| `fix/`      | Bug fix                                  |
| `docs/`     | Documentation only                       |
| `refactor/` | Code change with no behaviour change     |
| `perf/`     | Performance improvement                  |
| `test/`     | Adding or fixing tests only              |
| `build/`    | Build system, packaging, Dockerfiles, uv |
| `ci/`       | CI configuration / pre-commit            |
| `chore/`    | Maintenance, dependency bumps            |
| `security/` | Security fix                             |
| `revert/`   | Reverting a previous change              |

Examples:

- `feat/finops-agent-cost-anomaly`
- `fix/slack-channel-routing-finops`
- `docs/design-review-roadmap-update`
- `refactor/action-broker-policy-engine`
- `chore/uv-bump-0.5.11`

### Commit message convention — Conventional Commits

Every commit message follows the [Conventional Commits 1.0.0](https://www.conventionalcommits.org/) specification. The `conventional-pre-commit` hook enforces this on the `commit-msg` stage; commits with non-conforming messages are rejected.

```
<type>(<scope>): <subject>

<body>

<footer>
```

- **`<type>`** — required, one of: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`, `security`.
- **`<scope>`** — required. The component or module touched. Common scopes:
  `agents`, `orchestrator`, `sre`, `devsecops`, `platform`, `finops`,
  `slack-notifier`, `action-broker`, `terraform`, `eventing`, `governance`,
  `observability`, `agent-runtime`, `docs`, `contract`, `ci`, `deps`.
- **`<subject>`** — imperative mood, < 72 chars, no trailing period. "Add" not "Added", "Fix" not "Fixed".
- **`<body>`** — optional. Wrap at 72 columns. Explain _why_, not _how_.
- **`<footer>`** — optional. `BREAKING CHANGE: <description>` for breaking changes. Issue references like `Closes #123`.

#### Examples

```
feat(finops): add cost-anomaly detection for Cloud Run revisions
```

```
fix(slack-notifier): correct channel routing for critical platform signals

The routing table swapped #ops-platform and #ops-incidents for critical
platform signals; #ops-incidents is the correct channel per the routing
table in `services/slack-notifier/blockkit.py`.

Closes #142
```

```
refactor(action-broker)!: split policy engine into typed-rule + bounds-checker

BREAKING CHANGE: PolicyEngine.decide() now returns
Decision(tier, allowed, required_approvers, bounds, deny_reason); all
callers must handle the new shape.
```

The `!` after the scope marks a breaking change in the subject line.

### Pull-request process

1. **Open the PR against `main`.** Use **Draft** while still iterating.
2. **Fill in the PR template** completely (`.github/PULL_REQUEST_TEMPLATE.md`). The checklists are not decorative — reviewers will reject incomplete PRs.
3. **CI must pass.** All required pre-commit hooks, `terraform validate`, `pytest` (where applicable), and the secret-detection workflow.
4. **Reviews required.**
   - **1 reviewer** for changes scoped to `docs/`, tests, dev tooling, or non-prod-touching code.
   - **2 reviewers** for changes that touch `terraform/environments/prod/`, `services/action-broker/policy/action_classes.yaml` (autonomy-tier changes), any `schemas.py` (cross-component schema changes), or anything tagged with the `security` label.
5. **Squash-merge** when ready. The squash commit message becomes the canonical history entry.
6. **Delete the branch** after merge.

### Reverts

Reverts use `git revert <sha>` (not force-push) and follow Conventional Commits:

```
revert: feat(finops): add cost-anomaly detection for Cloud Run revisions

This reverts commit <SHA> because <reason>.
```

## Local development environment

This repository uses **[uv](https://docs.astral.sh/uv/)** for **all** Python package management. **Do not use `pip` directly.** uv replaces pip, pip-tools, virtualenv, pipx, and Poetry.

### Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Homebrew
brew install uv

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify with `uv --version` (≥ 0.5).

### Project layout

Repo-wide dev tools (ruff, mypy, pytest, pre-commit) are declared in the root `pyproject.toml`. Each Python component (`agents/`, `services/slack-notifier/`, `services/action-broker/`) is an **independent uv project** with its own `pyproject.toml` and its own `uv.lock`.

```
pyproject.toml                              ← repo-wide dev deps + shared tool config
agents/pyproject.toml                       ← agents runtime deps
services/slack-notifier/pyproject.toml      ← slack-notifier runtime deps
services/action-broker/pyproject.toml       ← action-broker runtime deps
```

Lockfiles (`uv.lock`) **are committed** to source control.

### Sync dependencies

```bash
# Root dev tools (ruff, mypy, pytest, pre-commit)
uv sync

# Each component
uv sync --directory agents
uv sync --directory services/slack-notifier
uv sync --directory services/action-broker
```

### Update / regenerate the lockfile

```bash
# in the component directory
uv lock

# or from repo root
uv lock --directory agents
```

### Add a dependency

```bash
cd <component>
uv add <package>            # runtime dep
uv add --dev <package>      # dev-only dep
# uv add automatically updates pyproject.toml AND uv.lock — commit both.
```

### Run things via uv

```bash
uv run pytest                                                # repo-wide tests
uv run --directory agents pytest                             # one component
uv run ruff check .                                          # lint
uv run ruff format .                                         # format (writes)
uv run ruff format --check .                                 # format (check only)
uv run mypy .                                                # type-check
uv run --directory services/slack-notifier uvicorn main:app --reload
```

### Pre-commit

```bash
uv tool install pre-commit
uv run pre-commit install --install-hooks
uv run pre-commit run --all-files                            # run all hooks
uv run pre-commit autoupdate                                 # bump hook versions
```

Pre-commit is **not optional** for contributors. CI runs the same hooks.

## What we welcome

- **Hardening of Terraform defaults** — least-privilege bindings, missing CMEK, missing `deletion_policy = "PREVENT"`, missing `auth_token_wo`, default-region drift.
- **Additional action-class executors** in `services/action-broker/executors/` — with a policy entry, tests, and a roadmap-tier rationale.
- **ADK 2.0 API confirmations** — every uncertain ADK import is currently flagged with `# ADK 2.0 API — confirm signature against adk.dev/2.0/`. PRs that replace these comments with verified signatures (and a doc-source URL in the PR description) are highly welcome.
- **Maturity updates** — when an `Announced-GA*` item from the design review reaches actual GA in-console, update Part 2.10's table and the relevant module.
- **Improvements to the observability surface** — new alert policies, dashboard widgets, SLOs, custom metrics.

## What we do not accept (without prior discussion)

- New runtime dependencies on non-Google managed services without an architectural justification in the PR.
- Direct writes to Google Cloud APIs from agent code (these **must** go through the Action Broker).
- Exported service-account keys, anywhere, ever (`google_service_account_key` resources will be rejected).
- Removal or weakening of `LIVE_MODE` / `LIVE_SLACK_ENABLED` guards.
- Provider version floats (`>= 7`) instead of pinned (`~> 7.34`).
- Sensitive identifiers committed to source — even in tests.
- **Local edits to `docs/AGENT_GOVERNANCE_FRAMEWORK.md`.** The framework is upstream-owned (framework §20.2). Raise the change upstream, then re-vendor the new version into this repo and update the `Conformance:` line in `README.md` plus the `docs/GOVERNANCE-MAPPING.md` attestation in the same PR.
- **Lowering or removing a §19 compliance attestation** without a corresponding entry in the roadmap (`docs/DESIGN-REVIEW.md` Part 10) explaining the regression and the path back.

## Governance changes (action-class tiers, policy, audit)

Changes that touch the **governance surface** trigger the 2-reviewer
rule automatically. These changes are:

- `services/action-broker/policy/action_classes.yaml` — autonomy tier
  or bounds for any action class.
- `services/action-broker/policy.py` — the policy engine itself.
- `aop_common/audit.py`, `aop_common/policy_client.py`,
  `aop_common/mcp_tools.py` — the cross-agent governance surfaces.
- `terraform/modules/governance/` — Model Armor, Org Policy, SCC v2.
- `terraform/modules/action-broker/` — per-action-class SAs, PAB, IAM.
- `agents/aop_common/schemas.py`, `services/*/schemas.py` — cross-component schemas and naming.
- `docs/GOVERNANCE-MAPPING.md` — attestation status.

For each, the PR must:

1. Cite the framework section the change implements or affects (e.g.
   "Implements framework §4.4 per-principal budgets").
2. Update `docs/GOVERNANCE-MAPPING.md` to reflect the new status.
3. Re-run any affected policy unit tests
   (`uv run --directory services/action-broker pytest tests/test_policy.py`).
4. Note in the PR description whether the change is a graduation up
   a tier, a tightening, or a fix — graduations require explicit
   sign-off from the named approver pool.

## Issues and security

- **Bugs, features, docs** — open an issue with the appropriate template under `.github/ISSUE_TEMPLATE/`.
- **Security vulnerabilities** — do **not** use issues. Follow `SECURITY.md` and use GitHub's private vulnerability reporting.
- **Open-ended questions** — use GitHub Discussions.

## Code of conduct

Be kind, be specific, assume good faith. Disagreement is expected and useful; personal attacks aren't.
