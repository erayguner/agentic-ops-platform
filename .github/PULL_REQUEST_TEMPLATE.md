<!--
Thanks for opening a PR! Please fill in the sections below.
Leave any section that genuinely does not apply, but do not delete it.
-->

## Summary
<!-- One short paragraph: what does this change do, and why? -->


## Linked items
<!-- Tickets, issues, RFCs, ADRs this PR addresses. Use GitHub keywords (Closes / Fixes / Resolves) to auto-close issues on merge. -->
- Closes #
- Related: <ADR, RFC, Jira / Linear ticket, design doc>


## Type of change
<!-- Tick all that apply: replace [ ] with [x]. -->
- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ Feature (non-breaking change that adds capability)
- [ ] 💥 Breaking change (fix or feature that alters existing behaviour)
- [ ] 📚 Documentation only
- [ ] 🔧 Refactor / chore / dependency update
- [ ] 🔒 Security fix
- [ ] ⚡ Performance improvement
- [ ] 🧪 Tests only


## Testing completed
<!-- Be specific: what did you actually run, and what was the outcome? -->
- [ ] `uv run pre-commit run --all-files` clean
- [ ] `terraform fmt -check -recursive` clean
- [ ] `terraform validate` passes in every root (`bootstrap/`, `environments/dev/`, `environments/prod/`)
- [ ] `uv run pytest` passes (or N/A — explain below)
- [ ] `uv run mypy .` passes (or N/A — explain below)
- [ ] Manual smoke test against `LIVE_MODE=false` services (describe below)
- [ ] No new secrets, real GCP identifiers, OAuth tokens, API keys, or estate-specific values introduced

**Details of testing:**
<!-- e.g., "Ran the Slack-notifier in dry-run mode and posted three sample OpsNotifications; verified Block Kit output matches §6.6." -->


## Risks and rollout
<!-- Anything a deployer must know to apply this safely. -->
- **Blast radius** — which environments / resources are touched?
- **Reversibility** — exact steps to roll this back if it goes wrong.
- **Feature flags / safe defaults** — is any new behaviour gated behind `LIVE_MODE`, `LIVE_SLACK_ENABLED`, an autonomy-tier policy entry, or a Terraform variable that defaults to "off"?
- **Migrations / data changes** — Pub/Sub schema bumped (v1 → v2)? Firestore data shape changed? BigQuery audit table evolved?
- **Required follow-up** — additional infra changes, policy PRs, doc updates, or eval re-runs that must land before this is "done"?


## Interface-contract impact
<!-- REQUIRED if this PR touches schemas, topic names, SAs, action classes, Slack channels, or any other cross-component contract surface. -->
- [ ] No change to `INTERFACE-CONTRACT.md`.
- [ ] `INTERFACE-CONTRACT.md` updated in this PR; downstream files updated atomically:
  - [ ] `agents/aop_common/schemas.py`
  - [ ] `services/slack-notifier/schemas.py`
  - [ ] `services/action-broker/schemas.py`
  - [ ] `terraform/modules/eventing/main.tf` (`google_pubsub_schema`)
  - [ ] `docs/DESIGN-REVIEW.md` Appendix C (schemas) or Part 6.6 (Slack message contract)


## Reviewer checklist
- [ ] Implementation follows the design principles in `docs/DESIGN-REVIEW.md` §3.1.
- [ ] No exported service-account keys; CI / dev identities use Workload Identity Federation.
- [ ] New write actions go through the Action Broker, **never** directly from agents.
- [ ] Any new `action_class` has a policy entry in `services/action-broker/policy/action_classes.yaml` and an autonomy tier consistent with §3.3.
- [ ] Slack message-shape changes match `OpsNotification v1` (Appendix C).
- [ ] `docs/DESIGN-REVIEW.md` updated where the architectural surface changed.
- [ ] `CHANGELOG.md` (if present) entry added under `## [Unreleased]`.
