# Changelog

All notable changes to the Agentic Operations Platform are recorded here.
This file is maintained by [release-please](https://github.com/googleapis/release-please);
do not edit it by hand — write [Conventional Commits](https://www.conventionalcommits.org/)
and release-please will generate the entries for you.

## [0.1.0] - 2026-05-26

### Features

- Reusable Terraform deployment framework with per-agent modules and an
  opt-in `aop-platform` composition module.
- Pre-flight validation script (`scripts/preflight.sh`) covering provider
  auth, required APIs, state backend, IAM, secrets, naming, and Org Policy.
- Examples: `full-dev`, `staging`, `prod-locked-down`, `minimal-sre-only`,
  `downstream-consumer`.
- Per-agent optional Cloud Scheduler triggers and Memory Bank variants.
- Terraform-native `check` blocks enforcing prod invariants (deletion
  prevention, warm pools, dataset-scoped FinOps IAM).
- release-please-driven semantic versioning and GitHub releases.
