# Changelog

All notable changes to the Agentic Operations Platform are recorded here.
This file is maintained by [release-please](https://github.com/googleapis/release-please);
do not edit it by hand — write [Conventional Commits](https://www.conventionalcommits.org/)
and release-please will generate the entries for you.

## [0.5.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.4.0...v0.5.0) (2026-06-04)


### Features

* **agent-runtime:** adopt Agent Engine features — memory retention, per-agent identity, labels ([8136190](https://github.com/erayguner/agentic-ops-platform/commit/8136190115f04f6643168b40cce1193a11cbaa77))
* **agent-runtime:** adopt Agent Engine provider features (memory retention, per-agent identity, labels) ([793d528](https://github.com/erayguner/agentic-ops-platform/commit/793d5282930ea0ee2752dae8d874f6575b9e14a5))

## [0.4.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.3.0...v0.4.0) (2026-06-04)


### Features

* **governance:** protect audit BigQuery dataset from deletion in prod ([43720f2](https://github.com/erayguner/agentic-ops-platform/commit/43720f24787abfb67b5f214b3a0f5ace48454295))


### Bug Fixes

* **slack-notifier:** close secret-redaction gaps ([d6b2bc9](https://github.com/erayguner/agentic-ops-platform/commit/d6b2bc910cb7836024dbbc339948f1422cc30e9c))


### Documentation

* correct version and path drift ([20d7132](https://github.com/erayguner/agentic-ops-platform/commit/20d713202f6e22e048bf68dfca4bb444ecf08704))

## [0.3.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.2.1...v0.3.0) (2026-06-04)


### Features

* **aibom:** add AI Bill of Materials and governance mapping ([b3a6315](https://github.com/erayguner/agentic-ops-platform/commit/b3a6315d0588d2f1f0627fc734bca74616984e83))

## [0.2.1](https://github.com/erayguner/agentic-ops-platform/compare/v0.2.0...v0.2.1) (2026-06-02)


### Bug Fixes

* **action-broker:** validate ID token audience in MCP auth ([bb04bd3](https://github.com/erayguner/agentic-ops-platform/commit/bb04bd3840989d3269de87670a3305cd523de966))

## [0.2.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.1.0...v0.2.0) (2026-05-27)


### Features

* **agents:** wire Developer Knowledge MCP into reasoner allow-lists ([b772ef1](https://github.com/erayguner/agentic-ops-platform/commit/b772ef1e8543d1520a7f532f821fd29231b12a40))
* **framework:** reusable terraform deployment framework for agentic ops ([331d1e2](https://github.com/erayguner/agentic-ops-platform/commit/331d1e266bd0a43d24e431d102aaa79e19178ad3))
* **framework:** reusable terraform deployment framework for agentic ops ([c6b9792](https://github.com/erayguner/agentic-ops-platform/commit/c6b9792c4dd3b6de79b992a1478b162f803da1b4))


### Bug Fixes

* **ci:** move matrix-scoped concurrency into the job ([061db58](https://github.com/erayguner/agentic-ops-platform/commit/061db58a04fdc71edb0d93ac277daf29f634730d))
* **ci:** pin trivy-action to v0.36.0 (with v-prefix) ([a1775ec](https://github.com/erayguner/agentic-ops-platform/commit/a1775ec1aef65e93ce2ed438b968b1079244be6a))
* **framework:** make terraform test CI-clean and cover every module ([89b9929](https://github.com/erayguner/agentic-ops-platform/commit/89b9929df8da31f2a6c9e4b20fc3fa6bc53a1277))
* green up terraform test + refresh action SHA pins ([cb4494f](https://github.com/erayguner/agentic-ops-platform/commit/cb4494f3650507a1a893ea02eb492600f5567d7f))
* **security:** clear CodeQL/Scorecard alerts in agents + services ([f4e09d4](https://github.com/erayguner/agentic-ops-platform/commit/f4e09d40ded5a797b367971237aa2d003736d5bb))
* **workflows:** use commit SHA for codeql-action, document release-please prereq ([595a3b4](https://github.com/erayguner/agentic-ops-platform/commit/595a3b433f643a1f081a337d80b87d653bf68f4b))
* **workflows:** use commit SHA for codeql-action; document release-please repo prereq ([ddccd21](https://github.com/erayguner/agentic-ops-platform/commit/ddccd2199b9b26d713b7bd52c0ceb04852ac4f47))


### Documentation

* **design-review:** drop estate-specific audit content ([8b4a638](https://github.com/erayguner/agentic-ops-platform/commit/8b4a638d88219adcf1bbe752058b86aa07fc254c))
* drop public-release sanitisation framing ([a0c04a2](https://github.com/erayguner/agentic-ops-platform/commit/a0c04a26d0c7811f875bd853d736213dce99c693))


### Build

* **deps:** bump the python-runtime group across 3 directories with 2 updates ([2566ef9](https://github.com/erayguner/agentic-ops-platform/commit/2566ef94fedd242b291aabf44fa89bbffb56108c))
* **deps:** bump the python-runtime group across 3 directories with 2 updates ([182b7c0](https://github.com/erayguner/agentic-ops-platform/commit/182b7c093b6b013a6a0a60b762c45fca62c859a5))
* **deps:** update uvicorn[standard] requirement ([99dda80](https://github.com/erayguner/agentic-ops-platform/commit/99dda8025a6daf43baf464fa52a7ef88bd69657f))
* **deps:** update uvicorn[standard] requirement ([7d4045e](https://github.com/erayguner/agentic-ops-platform/commit/7d4045ebf43f7ee07cd081282c36cd0ecdb32f56))
* **deps:** update uvicorn[standard] requirement from &gt;=0.32 to &gt;=0.48.0 in /services/action-broker ([e0250ab](https://github.com/erayguner/agentic-ops-platform/commit/e0250abd984a3fc405a967e18e05f1ed98d9c160))
* **deps:** update uvicorn[standard] requirement from &gt;=0.32 to &gt;=0.48.0 in /services/slack-notifier ([b322e03](https://github.com/erayguner/agentic-ops-platform/commit/b322e03e216eccf30b848c4374002a3981915c6b))

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
