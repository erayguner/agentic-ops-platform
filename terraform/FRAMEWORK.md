# AOP Terraform Deployment Framework

Reusable, modular Terraform for the Agentic Operations Platform. Lets a team
deploy any subset of the AOP agents (orchestrator, SRE, DevSecOps, Platform,
FinOps) plus the supporting eventing, governance, observability, action-broker,
and slack-notifier infrastructure — from this repo OR from a downstream
consumer repo — with consistent guard-rails.

## Table of contents

1. [Architecture](#architecture)
2. [Module catalogue](#module-catalogue)
3. [Quick start](#quick-start)
4. [Selecting agents](#selecting-agents)
5. [Per-agent scheduling and event triggers](#per-agent-scheduling-and-event-triggers)
6. [Pre-flight validation](#pre-flight-validation)
7. [Secure defaults](#secure-defaults)
8. [Observability + health checks](#observability--health-checks)
9. [Consuming from another repo](#consuming-from-another-repo)
10. [Release management](#release-management)
11. [Rollback runbook](#rollback-runbook)
12. [Compatibility with the legacy `agent-runtime` module](#compatibility-with-the-legacy-agent-runtime-module)

---

## Architecture

```text
                 ┌────────────────────────────────────────┐
                 │    aop-platform (composition module)   │
                 └──────────────┬─────────────────────────┘
                                │
   ┌────────────┬───────────────┴─────────────┬───────────────────┐
   │            │                             │                   │
   ▼            ▼                             ▼                   ▼
foundation  eventing                      governance         observability
   │            │                             │                   │
   ▼            ▼                             ▼                   ▼
   …      Pub/Sub topics                Model Armor,       dashboards, SLOs,
          schemas, DLQs,                 SCC notify,         alerts, uptime
          BQ audit table                 Org Policy            checks
                                       audit log sink

                                ┌──────── action-broker / slack-notifier ────┐
                                │  Cloud Run + per-action-class SAs + push   │
                                └─────────────────────────────────────────────┘

                                 ┌────────── agents/ (opt-in) ───────────────┐
                                 │ orchestrator  sre  devsecops  platform    │
                                 │                              finops       │
                                 └────────────────────────────────────────────┘
```

Every box is its own Terraform module under `terraform/modules/*`. The
composition module wraps all of them and exposes feature flags — drop a
flag to false and the underlying module is not instantiated at all.

## Module catalogue

| Module | Purpose | Default state |
|--------|---------|---------------|
| `modules/aop-platform` | Top-level composition (use this) | n/a |
| `modules/foundation` | VPC, Artifact Registry, Essential Contacts, API enable | `enable_foundation = true` |
| `modules/eventing` | Pub/Sub spine, schemas, DLQs, BQ audit table, Eventarc | `enable_eventing = true` |
| `modules/governance` | Model Armor, SCC notify, Org Policy, audit sink, Auditor role | `enable_governance = true` |
| `modules/observability` | Dashboards, alerts, log-based metrics, uptime checks, SLOs | `enable_observability = true` |
| `modules/action-broker` | Cloud Run broker + per-action-class SAs | `enable_action_broker = true` |
| `modules/slack-notifier` | Cloud Run notifier + Slack secrets | `enable_slack_notifier = true` |
| `modules/agents/_base` | Shared per-agent base (SA, engine, IAM, schedule, checks) | n/a |
| `modules/agents/orchestrator` | Ops Orchestrator agent | opt-in |
| `modules/agents/sre` | SRE agent | opt-in |
| `modules/agents/devsecops` | DevSecOps agent | opt-in |
| `modules/agents/platform` | Platform Engineering agent | opt-in |
| `modules/agents/finops` | FinOps agent | opt-in |
| `modules/agent-runtime` | Legacy monolithic agent module (kept for back-compat) | use new agents/ instead |

## Quick start

```bash
git clone https://github.com/erayguner/agentic-ops-platform.git
cd agentic-ops-platform/terraform/examples/full-dev
terraform init
terraform plan \
  -var="project_id=$PROJECT_ID" \
  -var="slack_auth_token=$SLACK_AUTH_TOKEN" \
  -var="slack_workspace_id=$SLACK_WORKSPACE_ID"
```

The four working examples are:

| Example | Posture |
|---------|---------|
| `terraform/examples/full-dev` | every component, every agent, dev defaults |
| `terraform/examples/minimal-sre-only` | only SRE, only what it needs |
| `terraform/examples/staging` | warm pools, every agent, no destroy lock |
| `terraform/examples/prod-locked-down` | warm pools, destroy lock, dataset-scoped IAM |
| `terraform/examples/downstream-consumer` | consume the framework from another repo |

## Selecting agents

The `enabled_agents` map controls which agents are deployed. Drop a key to
omit the agent entirely — its SA, IAM, reasoning engine, and schedule are not
created.

```hcl
enabled_agents = {
  sre       = {}                                  # default settings
  devsecops = { enable_memory_bank = true }       # turn on Memory Bank
  finops    = {                                   # custom schedule + labels
    schedule = {
      cron       = "0 6 * * *"
      target_uri = "https://finops-fanout.example.com/run"
    }
    labels = { cost_centre = "platform-finops" }
  }
}
```

Per-agent fields:

| Field | Default | Notes |
|-------|---------|-------|
| `enabled` | `true` | set to `false` to skip while keeping the map key |
| `enable_memory_bank` | `false` | uses the beta provider |
| `package_pickle_gcs_uri` | `""` | placeholder fails the framework's check block |
| `schedule` | `null` | Cloud Scheduler config (see below) |
| `labels` | `{}` | merged with the canonical AOP labels |

## Per-agent scheduling and event triggers

Two trigger surfaces are baked in:

1. **Cloud Scheduler** — set `schedule = { cron = "...", target_uri = "..." }`
   on the agent's entry in `enabled_agents` to provision a Cloud Scheduler
   job that POSTs to the target URI on a cron schedule, using the agent SA
   as the OIDC identity.
2. **Pub/Sub** — every agent already subscribes / publishes to the relevant
   canonical topics through the eventing module. The orchestrator subscribes
   to `ops.signals`; specialists publish `ops.findings`; everyone publishes
   `ops.notifications` and `ops.audit`. No extra configuration required.

## Pre-flight validation

`scripts/preflight.sh` covers the common pre-deployment gates:

```bash
# Framework-level only — runs anywhere, no GCP creds needed.
./scripts/preflight.sh

# Against a specific example or env root.
./scripts/preflight.sh terraform/examples/full-dev

# Skip individual sections via env vars.
AOP_SKIP_GCLOUD=1 ./scripts/preflight.sh terraform/examples/full-dev
AOP_SKIP_TFLINT=1 ./scripts/preflight.sh terraform/examples/full-dev
```

Categories of checks:

| Category | Implementation | Tools required |
|----------|----------------|----------------|
| Tooling presence | `aop::check_tool` | `terraform`, `tflint`, `jq` |
| `fmt` / `validate` / `tflint` / `trivy` / `checkov` | `aop::run_*` | matching binaries on PATH |
| Naming (project_id, region, env) | regex + placeholder check | none |
| ADC / gcloud auth | `gcloud auth application-default print-access-token` | `gcloud` |
| Project existence | `gcloud projects describe` | `gcloud` |
| Required APIs | `gcloud services list --enabled` cross-check | `gcloud` |
| State backend | `gcloud storage buckets describe` + versioning + UBLA | `gcloud` |
| WIF pool | `gcloud iam workload-identity-pools describe aop-ci-pool` | `gcloud` |
| Runner SA | `gcloud iam service-accounts describe sa-tf-runner-<env>` | `gcloud` |
| Required secrets | `gcloud secrets list` cross-check | `gcloud` |
| Org Policy | `gcloud org-policies list --project` | `gcloud` |

Outputs a `pass / warn / fail` summary; exit code is non-zero if any check
failed. CI uses it as a gate (`smoke` job in `.github/workflows/terraform.yml`).

## Secure defaults

Every per-agent module enforces these by construction:

- one SA per agent; **no exported keys**; write paths go through the Action Broker.
- `roles/owner` and `roles/editor` are rejected by `_base` variable validation.
- `ops.audit` publisher IAM is non-negotiable on every agent.
- `check` blocks fail the plan if:
  - the package URI still points at `gs://REPLACE_BUCKET/...`
  - the scheduler target is not HTTPS
  - the SA email is empty

The composition module adds environment-aware `check` blocks:

- `env = "prod"` MUST have `deletion_policy_prevent = true`
- `env = "prod"` MUST have `min_instance_count_broker >= 1`
- agents can only be enabled when `enable_eventing = true`
- FinOps in prod MUST set `finops_billing_export_bq_dataset_id` (no project-wide BQ fallback)

The action-broker module enforces:

- the broker SA holds no broad write IAM — only `iam.serviceAccountTokenCreator`
  on the per-action-class SAs
- each action class has a custom IAM role narrower than the matching predefined role
- `workflows_invoker_resource_pattern` lets prod fence the workflows.invoker
  grant by resource-name prefix

## Observability + health checks

- Cloud Run services use liveness probes on `/healthz`.
- Observability module creates uptime checks for the broker and notifier.
- Three alert policies ship by default:
  - Agent down (Agent Engine request count drops to zero for 5 minutes)
  - Decision latency p95 > 60s (15-minute rolling window)
  - Action rollback rate > 5% (log-based metric)
- Two notification channels (Slack primary + Pub/Sub redundant) for delivery
  resilience.
- Log-based metrics: token spend, policy denials, rollback count.
- A `ops-platform-overview` dashboard groups the above charts.

Plan-time `check` blocks across every module surface configuration drift
without requiring runtime probes.

## Consuming from another repo

```hcl
module "aop" {
  source = "git::https://github.com/erayguner/agentic-ops-platform.git//terraform/modules/aop-platform?ref=v0.5.2" # x-release-please-version

  project_id = "my-org-aop-dev"
  env        = "dev"
  region     = "europe-west2"

  enabled_agents = {
    sre       = {}
    devsecops = {}
  }

  essential_contacts_email = "team-oncall@example.com"
  slack_auth_token         = var.slack_auth_token
  slack_workspace_id       = var.slack_workspace_id
}
```

Pin a release tag (never a branch). Bump the tag in a PR so reviewers
can see the diff of the framework's CHANGELOG before adopting new behaviour.

The `terraform/examples/downstream-consumer/` directory contains the full
template, including the `backend.tf.example` and downstream-side IAM hook.

### Recommended downstream layout

```text
downstream-repo/
├── envs/
│   ├── dev/
│   │   ├── backend.tf       # GCS bucket for dev state
│   │   ├── main.tf          # module "aop" { source = "git::..." }
│   │   └── terraform.tfvars # placeholder values, no secrets
│   ├── staging/
│   └── prod/
├── scripts/
│   └── preflight.sh         # symlink or vendored copy
└── .github/workflows/
    └── terraform.yml        # mirrors AOP terraform.yml structure
```

## Release management

The framework uses [release-please](https://github.com/googleapis/release-please)
to drive semantic versions, the CHANGELOG, and GitHub releases:

- Configuration: `release-please-config.json`
- Manifest:      `.release-please-manifest.json`
- Workflow:      `.github/workflows/release-please.yml`
- Section map:   `feat → minor`, `fix → patch`, `feat!: → major`

Commits MUST follow [Conventional Commits](https://www.conventionalcommits.org/);
this is already enforced by the `conventional-pre-commit` commit-msg hook.

When release-please opens a release PR, reviewers should:

1. Inspect the generated `CHANGELOG.md` diff.
2. If accepted, merge it — the workflow cuts the GitHub Release on merge.
3. Downstream consumers bump `aop_framework_version` to the new tag.

## Rollback runbook

The framework's design favours **forward rollback** (revert + reapply) over
in-place destructive operations.

### Reverting a release

```bash
git revert -m 1 <merge-commit-of-release-pr>
git push
```

release-please will open a new patch release that undoes the previous one;
the downstream consumer just bumps to the new tag.

### Rolling back agent-specific changes

To withdraw an agent without destroying its SA (preserves audit trail):

```hcl
enabled_agents = {
  sre = { enabled = false }   # keeps the map key, but skips provisioning
}
```

Apply — the agent module count drops to zero, the SA is destroyed.

To withdraw a Cloud Scheduler trigger only:

```hcl
enabled_agents = {
  sre = { schedule = null }
}
```

### Rolling back a faulty action class

Action classes live in `terraform/modules/action-broker/main.tf`. To
temporarily disable an action class:

1. In your `main.tf`, override the broker's policy bounds (`policy/action_classes.yaml`)
   to set the class to `tier: 0` (recommend-only).
2. Apply. The custom IAM role is unchanged but the broker refuses to execute.
3. After the underlying bug is fixed, restore the tier and reapply.

### Destroy precautions

- `deletion_policy_prevent = true` in prod blocks Reasoning Engine destruction.
- Pub/Sub `ops.audit` is protected by topic-schema constraints and the BQ
  subscription's `deletion_protection`.
- The state bucket is created in `terraform/bootstrap` with `force_destroy = false`
  and CMEK.

If you absolutely must `terraform destroy` in prod:

1. Disable `deletion_policy_prevent` in a dedicated PR (single-purpose change).
2. Apply, run destroy, then re-enable `deletion_policy_prevent` in a follow-up.

## Compatibility with the legacy `agent-runtime` module

The existing `terraform/modules/agent-runtime` module is a monolithic deployment
that always creates all five agents. It remains supported for the existing
`terraform/environments/{dev,prod}/` roots so live state is not disturbed.

**Do not** use both `agent-runtime` AND the new `agents/*` modules in the same
GCP project — they would collide on `sa-<slug>` SA names and reasoning-engine
resources.

To migrate an existing environment to the new framework:

1. Add a `moved` block per resource pair (legacy → new path).
2. Run `terraform plan` and confirm no destroys are proposed.
3. Apply in a single PR.

A migration example is on the roadmap (`docs/migration-from-agent-runtime.md`)
and will be added when the existing dev/prod roots are converted.
