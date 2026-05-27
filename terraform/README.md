# AOP Terraform Reference Scaffold

Reference IaC for the Agentic Operations Platform. This is a validate-ready skeleton — not a deployed system. All `REPLACE_*` placeholders must be substituted before applying.

> **New: reusable deployment framework.** See [`FRAMEWORK.md`](./FRAMEWORK.md)
> for the per-agent modules + `aop-platform` composition + examples that let
> downstream consumers opt into specific agent types. The legacy
> `modules/agent-runtime` and `environments/{dev,prod}` roots below remain
> supported for the existing scaffolded environments.

## Layout

```text
terraform/
├── bootstrap/                 # One-time, hand-run. Creates state buckets + WIF.
├── FRAMEWORK.md               # Reusable deployment framework guide.
├── modules/
│   ├── foundation/            # VPC, Artifact Registry, Essential Contacts, API enablement
│   ├── governance/            # Model Armor, SCC v2, Org Policy, audit sink, Auditor role
│   ├── eventing/              # Pub/Sub topics + schemas + DLQs, BQ audit table, Eventarc
│   ├── observability/         # Notification channels, alerts, dashboards, log metrics, SLOs
│   ├── agent-runtime/         # Legacy monolithic agent module (still wired into envs/{dev,prod})
│   ├── action-broker/         # Cloud Run broker, per-action-class SAs, push subscription
│   ├── slack-notifier/        # Cloud Run notifier, secrets, Pub/Sub push subscription
│   ├── agents/                # Per-agent modules (opt-in)
│   │   ├── _base/             # Shared SA + reasoning engine + IAM + optional Cloud Scheduler
│   │   ├── orchestrator/
│   │   ├── sre/
│   │   ├── devsecops/
│   │   ├── platform/
│   │   └── finops/
│   └── aop-platform/          # Top-level composition (selectable agents + feature flags)
├── environments/
│   ├── dev/                   # Composes all modules for ops-agents-dev (legacy path)
│   └── prod/                  # Composes all modules for ops-agents-prod (legacy path)
├── examples/                  # Working examples consuming the new composition module
│   ├── full-dev/
│   ├── minimal-sre-only/
│   ├── staging/
│   ├── prod-locked-down/
│   └── downstream-consumer/
└── tests/                     # Native `terraform test` suite for the framework
```

## Apply order

1. `bootstrap/` — hand-run once. Outputs state bucket names and WIF provider name.
2. `environments/dev/` — apply via CI (GitHub Actions + WIF).
3. `environments/prod/` — apply via CI, two-approver merge gate.

Modules are not applied independently — they are composed by the environment roots.

## Provider strategy

- Primary: `hashicorp/google ~> 7.33`
- Beta: `hashicorp/google-beta ~> 7.33` — used **only** for `context_spec` on `google_vertex_ai_reasoning_engine` (Memory Bank). Every `provider = google-beta` usage is annotated with an inline comment.

## Terraform version

`required_version = ">= 1.10"`. The scaffold was validated on Terraform 1.14.0. The DESIGN-REVIEW recommends >= 1.15 in production.

## CI expectations

```text
PR:  terraform fmt -check | terraform validate | terraform plan (dev)
     gcloud beta terraform vet | OPA/Conftest | cost estimate
     >= 2 reviewers required (CODEOWNERS enforces prod)

Merge: terraform apply (dev) via WIF → sa-tf-runner-dev
       (manual gate) terraform apply (prod) via WIF → sa-tf-runner-prod
```

## Naming conventions

All names follow the project's naming conventions. Key rules:

- Service accounts: `sa-<component>` and `sa-action-<class-slug>`
- Pub/Sub topics: `ops.<phase>` with `.dlq` suffix for dead-letter topics
- Resources carry labels: `app=aop`, `env=<env>`, `component=<name>`, `managed_by=terraform`
- No `roles/owner` or `roles/editor` granted anywhere
- No `google_service_account_key` resources anywhere
