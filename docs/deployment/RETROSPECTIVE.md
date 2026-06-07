# Retrospective — Terraform deploy/destroy validation & hardening

**Effort:** prove the Agentic Operations Platform deploys end-to-end from
Terraform and tears down cleanly on GCP, then harden it for repeatable,
auditable, cost-aware, secure, cleanly-removable deploys.
**Window:** 2026-06-06 → 2026-06-07 · **Target:** `agentic-ops-platform` (europe-west2)
**Shipped:** **v0.7.0** (PRs #26, #27; release #28).

---

## TL;DR

We took a *validate-ready skeleton* and proved it has a working, fully-reversible
Terraform lifecycle. Two full deploy→verify→destroy cycles ran cleanly (103 then
106 resources, idempotent, zero residual). **18 findings** were fixed or gated
with rationale; the supporting platform now deploys for **~$1–3/mo** and destroys
to nothing. The agent tier remains the one genuinely-unfinished piece (ADK
builders are stubs; Agent Engine isn't in europe-west2) — its deploy path is
wired + documented but intentionally not run.

The single biggest lesson: **`terraform validate` proves nothing about
apply-readiness.** Every real blocker surfaced only at `apply` (and a few only at
`destroy`).

---

## What we set out to do vs. what we found

| Expectation | Reality |
|-------------|---------|
| "Deploy the project" | The repo is a **skeleton**; a literal full apply fails at ~6 independent points |
| `validate` passing ⇒ deployable | `validate` passed on `bootstrap`/`dev`/`prod`; apply failed repeatedly |
| Cost is the concern to research up front | Infra is ~free; **cost is entirely Gemini tokens** (agents), which never ran |
| Destroy is the easy part | Destroy surfaced its own class of bugs (deletion protection, sink-created tables, dependency ordering) |
| Agents just need deploying | The agent **builders raise `NotImplementedError`** — they can't be constructed, let alone deployed |

---

## What went well (keep doing)

- **Cost-first, HITL checkpoints.** Researching cost before spending, and pausing
  at genuine forks (scope, region, don't-deploy-agents, cut-release) kept the
  spend at pennies and avoided deploying Preview/stub components that would have
  added cost and risk for no value.
- **Staged apply for image-dependent infra.** `apply -target=module.foundation`
  → build & push images → full `apply` is the right pattern when Cloud Run needs
  an image that an in-tree resource (Artifact Registry) must create first.
- **Verify-by-redeploy.** After fixing the gated items, a *second* full
  deploy→destroy cycle proved them (B1 BigQuery subscription) rather than
  trusting `validate`. This is what caught that the SLO still couldn't create.
- **Local state for a teardown-clean validation.** Avoided permanently
  littering the project with undeletable KMS keyrings (which `bootstrap` would
  have created), so `destroy` truly left zero residual.
- **Document-as-you-go.** The living `DEPLOYMENT-LOG.md` (commands, errors,
  fixes, decisions) made the retro and the PRs writeable from fact, not memory.
- **Backward-compatible hardening.** Every module change defaulted to prior
  behaviour, so `dev`/`prod` kept validating throughout.

---

## What went wrong / what we learned (the meat)

### Terraform / GCP technical lessons

1. **`validate` ≠ apply-ready.** Validate only checks schema. No-org
   constraints, Preview APIs, missing images, IAM gaps, and schema mismatches
   are all invisible to it. → *Gate a real `plan`/`apply` (sandbox project) in
   CI, not just `validate`.*
2. **GCP eventual consistency is real and bites monitoring.** Alerts/SLOs that
   reference **labels of just-created** log-based metrics or uptime checks 404
   with "could take up to 10 minutes… try again soon." A *second* apply fixes
   it. → *Treat metric-dependent monitoring as 2nd-day, or add explicit waits;
   expect a re-apply on first stand-up.*
3. **SLOs can't be created against a service with no metric history.** A fresh,
   never-invoked, scale-to-zero (and internal-ingress) service emits nothing, so
   any metric SLI fails. → *SLOs are inherently 2nd-day; base them on Cloud Run
   request metrics once there's traffic.*
4. **Data sources break credential-less `terraform test`.** A `data` block is
   read at *plan* time against the live API; the plan-only test (fake token)
   fails on it. → *Gate API-reading data sources behind the feature flag of
   whatever they serve, and disable that path in plan-only tests.* (This one bit
   us twice: once at apply, once as the CI failure during babysitting.)
5. **Provider defaults can silently block `destroy`.** `google_cloud_run_v2_service`
   defaults `deletion_protection = true` in provider v7. → *Set it explicitly;
   default false for ephemeral/dev.*
6. **Enable APIs before the resources that need them.** Resources without
   `depends_on = [google_project_service…]` race the enablement → "API has not
   been used in project before." → *Order resources after their API.*
7. **Sinks create resources Terraform doesn't manage.** The `_AllLogs`→BigQuery
   sink auto-creates per-log tables in the audit dataset, blocking dataset
   `destroy`. → *`delete_contents_on_destroy` on log-sink destination datasets
   in non-prod.*
8. **Cross-string references need explicit `depends_on`.** An alert that
   references a log-metric *by type string* has no dependency edge, so `destroy`
   tries to delete the metric while the alert still uses it. → *Add `depends_on`
   when the coupling is by name/string, not resource reference.*
9. **Pub/Sub→BigQuery subscriptions need two things:** the Pub/Sub service-agent
   granted BigQuery `dataEditor`/`metadataViewer`, **and** schema compatibility —
   with `use_topic_schema=true` the AVRO field types must match the BQ columns
   (a repeated AVRO field can't map to a scalar `JSON` column).
10. **API shape gotchas:** Essential Contacts is **one contact per email** with a
    list of categories (not N contacts sharing an email); a Cloud Billing budget
    must use the **billing account's currency** (GBP here, not USD) and a ≤60-char
    display name; uptime checks need **≥3 regions**; a log-metric `value_extractor`
    requires a **`DISTRIBUTION`** metric.
11. **BuildKit Dockerfiles need a Cloud Build config.** `gcloud builds submit
    --tag` uses a non-BuildKit builder and fails on `RUN --mount=…`. → *Use a
    `cloudbuild.yaml` with `DOCKER_BUILDKIT=1`.*
12. **User ADC has no quota project.** Some APIs (e.g. Essential Contacts) 403
    without one. → *Set `user_project_override = true` + `billing_project` on the
    provider (keeps the fix in code, not in a per-machine `gcloud` step).*

### Environment / architecture lessons

13. **No-organization is a hard constraint.** Org Policy and SCC (all tiers,
    including free Standard) are organization-scoped and simply cannot run on a
    standalone project. → *Gate org-scoped resources behind `org_id != ""`.*
14. **Preview/region limits.** Vertex AI Agent Engine is region-limited and not
    available in europe-west2 — deploying agents forces an EU-residency vs.
    availability tradeoff.
15. **State backend is a prerequisite layer, not a destroyable resource.**
    `bootstrap` creates KMS keyrings/keys that **GCP never deletes** and a
    `force_destroy=false` bucket — so "fully destroyable" applies to the
    *platform*, not its state backend. Local state sidesteps this for validation.

### Process / working-method lessons

16. **Run the full test suite locally before pushing.** Both CI failures during
    babysitting (`terraform test`, then `ruff format`) were **avoidable** — they'd
    have been caught by running `terraform test` and `ruff format --check`
    locally before the first push. *Fast feedback locally > waiting on CI.*
17. **Stacked PRs: fix on the base.** The `terraform test` failure lived in the
    base PR (#26); fixing it there and merging the base into the stacked PR (#27)
    is cleaner than patching the tip.
18. **Changing a PR's base doesn't re-trigger CI.** A `pull_request` run needs an
    `opened`/`synchronize`/`reopened` event; after auto-retarget, a close/reopen
    (or a push) is required to get checks to run.
19. **Gating-with-rationale is a legitimate finding,** not a cop-out — provided
    the *why* and the *re-enable path* are documented (which `enable_*` flag, what
    prerequisite). It keeps the deploy green and honest.

---

## Root-cause themes

Most of the 18 findings collapse into five themes:

- **Skeleton ≠ deployable** — placeholders (pickle URIs, container images,
  secrets, REPLACE_* tfvars) and stub code that `validate` happily accepts.
- **Eventual consistency** — metric/label/descriptor propagation makes some
  monitoring resources inherently 2nd-day.
- **Environment assumptions** — the scaffold assumed an organization, a region
  with Agent Engine, and live Slack/agent traffic; none held.
- **Lifecycle asymmetry** — things that apply fine don't necessarily destroy
  fine (deletion protection, sink tables, string-coupled dependencies).
- **Test fidelity** — credential-less plan-only tests can't exercise data
  sources or anything needing live metric data.

---

## Key decisions (and why)

| Decision | Why |
|----------|-----|
| Deploy a **subset** via a dedicated `sandbox` root | The literal full deploy can't succeed; the subset proves the lifecycle |
| **Local** Terraform state for validation | Destroy leaves zero residual (no permanent KMS/bucket) |
| **Gate** agents / Org Policy / SCC / Model Armor / Eventarc | Infeasible (no org / Preview / no endpoint) or zero-value at rest |
| **Don't deploy the agent tier** | Builders are stubs; Agent Engine not in-region; billable Preview for no value |
| **Wire** `deploy.py` + document the path anyway | A real deploy is then one documented step away once builders exist |
| Cut **v0.7.0** | The hardening + validation belong in a release for downstream consumers |

---

## Metrics

- **Resources:** 103 (cycle 1) / 106 (cycle 2) deployed, idempotent, fully destroyed.
- **Findings:** 18 (fixed or gated-with-rationale).
- **Deploy iterations to green:** ~5 apply passes (each surfaced a distinct real bug).
- **Cost:** validation runs ≈ a few pence; steady-state infra ~$1–3/mo; agents-active dev ~$58/mo.
- **CI:** `terraform test` 33/33; PR #26 37 checks green; PR #27 37 checks green.
- **Residual after teardown:** enabled APIs + Google service agents only (documented, $0).
- **PRs:** #26, #27 merged; #28 release → **v0.7.0**.

---

## Action items / follow-ups

| # | Item | Status |
|---|------|--------|
| 1 | Implement the ADK 2.1 `build_<agent>()` WorkflowAgent graphs | open (the real blocker for agents) |
| 2 | Re-enable `enable_bq_audit_subscription` in roots (B1 fixed) | ready — schema reconciled |
| 3 | Rework the availability SLO onto Cloud Run request metrics; un-gate `enable_slo` | open |
| 4 | Add an orchestrator Cloud Run ingest endpoint, then wire the Eventarc triggers | open (architectural) |
| 5 | Choose a supported Agent Engine region (us-central1 / europe-west1) or EU multi-region for agents | open (decision) |
| 6 | Add a sandbox-project `plan`/`apply` gate to CI (catch apply-only failures pre-merge) | recommended |
| 7 | Raise the budget alert before enabling busy agents | when agents go live |

---

## If we did it again

1. Stand up a throwaway sandbox project and run `apply` early — don't trust
   `validate`.
2. Run `terraform test` + `ruff` locally before every push.
3. Expect monitoring (alerts/SLOs) to need a second apply; plan for it.
4. Decide region + org posture up front (they gate whole modules).
5. Keep the deploy log live from the first command.

## See also

[`README.md`](./README.md) · [`DEPLOYMENT-LOG.md`](./DEPLOYMENT-LOG.md) (findings F1–F18) ·
[`REQUIRED-APIS.md`](./REQUIRED-APIS.md) · [`COST-ESTIMATE.md`](./COST-ESTIMATE.md) ·
[`GCLOUD-COMMANDS.md`](./GCLOUD-COMMANDS.md) · [`AGENT-DEPLOY.md`](./AGENT-DEPLOY.md) ·
PRs [#26], [#27], [#28] · release **v0.7.0**.
