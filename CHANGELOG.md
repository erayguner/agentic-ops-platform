# Changelog

All notable changes to the Agentic Operations Platform are recorded here.
This file is maintained by [release-please](https://github.com/googleapis/release-please);
do not edit it by hand — write [Conventional Commits](https://www.conventionalcommits.org/)
and release-please will generate the entries for you.

## [0.8.1](https://github.com/erayguner/agentic-ops-platform/compare/v0.8.0...v0.8.1) (2026-06-08)


### Build

* **deps:** bump the python-runtime group across 3 directories with 5 updates ([1189548](https://github.com/erayguner/agentic-ops-platform/commit/118954838bb4a2bc413ce7c96d9a767c282a4f7e))
* **deps:** bump the python-runtime group across 3 directories with 5 updates ([63a55b6](https://github.com/erayguner/agentic-ops-platform/commit/63a55b6039cac58623c05dea2b5472b3b6294d55))
* **deps:** bump the terraform group across 3 directories with 2 updates ([bb56da9](https://github.com/erayguner/agentic-ops-platform/commit/bb56da933fc0c61e891458388c07931e131f2221))
* **deps:** bump the terraform group across 3 directories with 2 updates ([20ed273](https://github.com/erayguner/agentic-ops-platform/commit/20ed273eac5308c6d19002dc066e2b25cc03404d))
* **deps:** update uvicorn[standard] requirement ([4c76711](https://github.com/erayguner/agentic-ops-platform/commit/4c767111962011b57ad6831b392e630275fa6001))
* **deps:** update uvicorn[standard] requirement ([e1bdecb](https://github.com/erayguner/agentic-ops-platform/commit/e1bdecbf6c054ee52471e176e4ef2ed7f287d711))
* **deps:** update uvicorn[standard] requirement from &gt;=0.48.0 to &gt;=0.49.0 in /services/action-broker ([ac342f0](https://github.com/erayguner/agentic-ops-platform/commit/ac342f057d9aedcb4e8bad6c5b866851107eec6d))
* **deps:** update uvicorn[standard] requirement from &gt;=0.48.0 to &gt;=0.49.0 in /services/slack-notifier ([c3e906a](https://github.com/erayguner/agentic-ops-platform/commit/c3e906a7d21abe308c9b9a09324ef8fe8130a2dc))

## [0.8.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.7.1...v0.8.0) (2026-06-07)

### Features

- **agents:** read-only Google Cloud MCP servers for the agents (least-privilege) ([c164173](https://github.com/erayguner/agentic-ops-platform/commit/c164173186449c984b3b01ead2656467989f035a))

## [0.7.1](https://github.com/erayguner/agentic-ops-platform/compare/v0.7.0...v0.7.1) (2026-06-07)

### Documentation

- **deployment:** add deploy-validation retrospective / lessons learned ([8494ae9](https://github.com/erayguner/agentic-ops-platform/commit/8494ae9510c6786c8a2ad7958ec25010ab234463))
- **deployment:** deploy-validation retrospective / lessons learned ([8b148b6](https://github.com/erayguner/agentic-ops-platform/commit/8b148b6071411b49c85f5ed618aa78effe3ade07))

## [0.7.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.6.0...v0.7.0) (2026-06-07)

### Features

- **agents:** wire agent_engines.create() deploy path + agent-deploy runbook ([e7a3eb5](https://github.com/erayguner/agentic-ops-platform/commit/e7a3eb553ac4c2bd5ca725e3d12e44e5f4992330))
- **terraform:** deploy/destroy validation root + module hardening for clean lifecycle ([e2ac0e1](https://github.com/erayguner/agentic-ops-platform/commit/e2ac0e18165236697c51c241f0fbc4a070540263))
- **terraform:** deploy/destroy validation root + module hardening for clean lifecycle ([c559f3f](https://github.com/erayguner/agentic-ops-platform/commit/c559f3feeb53ed5df482bf262b7a7a1fd5d33c7a))

### Bug Fixes

- **eventing:** gate google_project data source so terraform test (plan, no creds) passes ([2de6a39](https://github.com/erayguner/agentic-ops-platform/commit/2de6a397ae1698611ee2c7376cf119869907cd78))
- **terraform:** reconcile audit BQ schema, rework SLO SLI, wire dev/prod gating ([b460c46](https://github.com/erayguner/agentic-ops-platform/commit/b460c46adc933a250a9285602954995b243fc898))
- **terraform:** un-gate audit BQ subscription, rework SLO SLI, wire dev/prod gating ([a8e87ae](https://github.com/erayguner/agentic-ops-platform/commit/a8e87aecb77f199343d6cf96aaa78cbf9b1c46fe))

## [0.6.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.5.2...v0.6.0) (2026-06-06)

### Features

- implement first-pass triage and dwell time metrics ([212f2af](https://github.com/erayguner/agentic-ops-platform/commit/212f2af883dd047640424f4693e76d652a6e6ca2))

## [0.5.2](https://github.com/erayguner/agentic-ops-platform/compare/v0.5.1...v0.5.2) (2026-06-05)

### Bug Fixes

- **terraform:** remediate checkov 3.2.531 findings (44 -&gt; 0) ([17f2fdf](https://github.com/erayguner/agentic-ops-platform/commit/17f2fdf9ab29ef8b15799d897168f188e67ca5dc))
- **terraform:** remediate checkov 3.2.531 findings (44 → 0) ([6d41ee7](https://github.com/erayguner/agentic-ops-platform/commit/6d41ee7a4d1ade846002223fb8343aae54c9771f))

## [0.5.1](https://github.com/erayguner/agentic-ops-platform/compare/v0.5.0...v0.5.1) (2026-06-05)

### Refactoring

- **action-broker:** hoist duplicated Outcome dataclass to the package ([edf81d7](https://github.com/erayguner/agentic-ops-platform/commit/edf81d7b5bf26bb7ddfe100062048536d0166590))

### Documentation

- refresh agent-runtime README and AIBOM for v0.5.0 ([0dc164e](https://github.com/erayguner/agentic-ops-platform/commit/0dc164e1fa40f2a5701dcbc333196a4f983412f9))

## [0.5.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.4.0...v0.5.0) (2026-06-04)

### Features

- **agent-runtime:** adopt Agent Engine features — memory retention, per-agent identity, labels ([8136190](https://github.com/erayguner/agentic-ops-platform/commit/8136190115f04f6643168b40cce1193a11cbaa77))
- **agent-runtime:** adopt Agent Engine provider features (memory retention, per-agent identity, labels) ([793d528](https://github.com/erayguner/agentic-ops-platform/commit/793d5282930ea0ee2752dae8d874f6575b9e14a5))

## [0.4.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.3.0...v0.4.0) (2026-06-04)

### Features

- **governance:** protect audit BigQuery dataset from deletion in prod ([43720f2](https://github.com/erayguner/agentic-ops-platform/commit/43720f24787abfb67b5f214b3a0f5ace48454295))

### Bug Fixes

- **slack-notifier:** close secret-redaction gaps ([d6b2bc9](https://github.com/erayguner/agentic-ops-platform/commit/d6b2bc910cb7836024dbbc339948f1422cc30e9c))

### Documentation

- correct version and path drift ([20d7132](https://github.com/erayguner/agentic-ops-platform/commit/20d713202f6e22e048bf68dfca4bb444ecf08704))

## [0.3.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.2.1...v0.3.0) (2026-06-04)

### Features

- **aibom:** add AI Bill of Materials and governance mapping ([b3a6315](https://github.com/erayguner/agentic-ops-platform/commit/b3a6315d0588d2f1f0627fc734bca74616984e83))

## [0.2.1](https://github.com/erayguner/agentic-ops-platform/compare/v0.2.0...v0.2.1) (2026-06-02)

### Bug Fixes

- **action-broker:** validate ID token audience in MCP auth ([bb04bd3](https://github.com/erayguner/agentic-ops-platform/commit/bb04bd3840989d3269de87670a3305cd523de966))

## [0.2.0](https://github.com/erayguner/agentic-ops-platform/compare/v0.1.0...v0.2.0) (2026-05-27)

### Features

- **agents:** wire Developer Knowledge MCP into reasoner allow-lists ([b772ef1](https://github.com/erayguner/agentic-ops-platform/commit/b772ef1e8543d1520a7f532f821fd29231b12a40))
- **framework:** reusable terraform deployment framework for agentic ops ([331d1e2](https://github.com/erayguner/agentic-ops-platform/commit/331d1e266bd0a43d24e431d102aaa79e19178ad3))
- **framework:** reusable terraform deployment framework for agentic ops ([c6b9792](https://github.com/erayguner/agentic-ops-platform/commit/c6b9792c4dd3b6de79b992a1478b162f803da1b4))

### Bug Fixes

- **ci:** move matrix-scoped concurrency into the job ([061db58](https://github.com/erayguner/agentic-ops-platform/commit/061db58a04fdc71edb0d93ac277daf29f634730d))
- **ci:** pin trivy-action to v0.36.0 (with v-prefix) ([a1775ec](https://github.com/erayguner/agentic-ops-platform/commit/a1775ec1aef65e93ce2ed438b968b1079244be6a))
- **framework:** make terraform test CI-clean and cover every module ([89b9929](https://github.com/erayguner/agentic-ops-platform/commit/89b9929df8da31f2a6c9e4b20fc3fa6bc53a1277))
- green up terraform test + refresh action SHA pins ([cb4494f](https://github.com/erayguner/agentic-ops-platform/commit/cb4494f3650507a1a893ea02eb492600f5567d7f))
- **security:** clear CodeQL/Scorecard alerts in agents + services ([f4e09d4](https://github.com/erayguner/agentic-ops-platform/commit/f4e09d40ded5a797b367971237aa2d003736d5bb))
- **workflows:** use commit SHA for codeql-action, document release-please prereq ([595a3b4](https://github.com/erayguner/agentic-ops-platform/commit/595a3b433f643a1f081a337d80b87d653bf68f4b))
- **workflows:** use commit SHA for codeql-action; document release-please repo prereq ([ddccd21](https://github.com/erayguner/agentic-ops-platform/commit/ddccd2199b9b26d713b7bd52c0ceb04852ac4f47))

### Documentation

- **design-review:** drop estate-specific audit content ([8b4a638](https://github.com/erayguner/agentic-ops-platform/commit/8b4a638d88219adcf1bbe752058b86aa07fc254c))
- drop public-release sanitisation framing ([a0c04a2](https://github.com/erayguner/agentic-ops-platform/commit/a0c04a26d0c7811f875bd853d736213dce99c693))

### Build

- **deps:** bump the python-runtime group across 3 directories with 2 updates ([2566ef9](https://github.com/erayguner/agentic-ops-platform/commit/2566ef94fedd242b291aabf44fa89bbffb56108c))
- **deps:** bump the python-runtime group across 3 directories with 2 updates ([182b7c0](https://github.com/erayguner/agentic-ops-platform/commit/182b7c093b6b013a6a0a60b762c45fca62c859a5))
- **deps:** update uvicorn[standard] requirement ([99dda80](https://github.com/erayguner/agentic-ops-platform/commit/99dda8025a6daf43baf464fa52a7ef88bd69657f))
- **deps:** update uvicorn[standard] requirement ([7d4045e](https://github.com/erayguner/agentic-ops-platform/commit/7d4045ebf43f7ee07cd081282c36cd0ecdb32f56))
- **deps:** update uvicorn[standard] requirement from &gt;=0.32 to &gt;=0.48.0 in /services/action-broker ([e0250ab](https://github.com/erayguner/agentic-ops-platform/commit/e0250abd984a3fc405a967e18e05f1ed98d9c160))
- **deps:** update uvicorn[standard] requirement from &gt;=0.32 to &gt;=0.48.0 in /services/slack-notifier ([b322e03](https://github.com/erayguner/agentic-ops-platform/commit/b322e03e216eccf30b848c4374002a3981915c6b))

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
