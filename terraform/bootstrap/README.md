# bootstrap

One-time, hand-run module. Creates the infrastructure required before any other AOP Terraform root can run:

- GCS state buckets (`aop-tfstate-dev`, `aop-tfstate-prod`) with versioning and CMEK.
- KMS keyrings and keys (90-day rotation) for state bucket encryption.
- Workload Identity Federation pool (`aop-ci-pool`) and GitHub Actions OIDC provider.
- `sa-tf-runner-dev` and `sa-tf-runner-prod` service accounts, bound to the WIF pool. No exported keys ever.

## State

Bootstrap uses **local state** (no backend block). Its state file lives at `terraform/bootstrap/terraform.tfstate`. Do not commit this file — it is `.gitignore`d at the repo level.

## Prerequisites

1. A GCP project exists and you have `Owner` or `roles/iam.admin` + `roles/storage.admin` + `roles/cloudkms.admin`.
2. `gcloud auth application-default login` is set for your personal account.
3. The `github_org` and `github_repo` variables are set to match your CI repository.

## Run once

```bash
cd terraform/bootstrap

terraform init
terraform plan -var="project_id=<your-project>" -var="github_org=<org>" -var="github_repo=<repo>"
terraform apply -var="project_id=<your-project>" -var="github_org=<org>" -var="github_repo=<repo>"
```

## After apply — move state

Bootstrap's own state stays local. The subsequent environment roots (`environments/dev/`, `environments/prod/`) use the GCS backend this module just created.

If you later need to import bootstrap resources into a remote backend, use `terraform state mv` or the `moved` block pattern. Do not attempt `terraform init -migrate-state` for the bootstrap module itself.

## WIF posture — per-environment scoping

The WIF provider trusts GitHub Actions OIDC tokens issued for **this repo only**, and the runner SAs are tightly scoped per environment:

| SA | Impersonatable from | Use |
|----|---------------------|-----|
| `sa-tf-runner-dev` | Any workflow run satisfying the provider's `attribute_condition` (push to `main`, or PR event, or run declaring any environment) | `dev` plans & applies |
| `sa-tf-runner-prod` | **ONLY** workflow runs that declare the GitHub Actions environment named `${var.prod_github_environment}` (default `deploy-prod`) | `prod` applies |

The provider's `attribute_condition` enforces:

```
assertion.repository == "<org>/<repo>"
&& (
  assertion.ref == "refs/heads/main"
  || assertion.event_name == "pull_request"
  || assertion.environment != ""
)
```

— so a push to a feature branch *without* a PR or declared environment cannot impersonate either runner.

### Required GitHub-side setup (one-time per repository)

The `sa-tf-runner-prod` binding is only useful if the GitHub side enforces a corresponding gate. In the repository's **Settings → Environments**:

1. **Create environment `deploy-prod`** (or whatever you set `prod_github_environment` to).
2. Under **Required reviewers**, add at least two reviewers from the platform / security teams. GitHub will require a manual click-through before each prod-tagged workflow run can proceed.
3. Under **Deployment branches and tags**, restrict to **`main`** (no feature branches).
4. Optionally set a **wait timer** (e.g. 5 minutes) for cooling-off.
5. Set repository secret **`WIF_PROVIDER`** to the `wif_provider_name` output.
6. Set repository secret **`TF_RUNNER_SA_PROD`** to `tf_runner_sa_emails["prod"]`.
7. Set repository secret **`TF_RUNNER_SA_DEV`** to `tf_runner_sa_emails["dev"]`.

Without the GitHub environment configured, prod applies will fail with `unable to impersonate` because no run will satisfy `attribute.environment == "deploy-prod"`.

## GitHub Actions — WIF authentication snippet

Dev plan/apply (no environment declared):

```yaml
jobs:
  dev-apply:
    permissions:
      id-token: write
      contents: read
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.TF_RUNNER_SA_DEV }}
```

Prod apply (gated by the `deploy-prod` GitHub Environment):

```yaml
jobs:
  prod-apply:
    environment: deploy-prod          # ← required to satisfy WIF principalSet binding
    permissions:
      id-token: write
      contents: read
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.TF_RUNNER_SA_PROD }}
```

## Inputs

| Name | Type | Default | Required |
|------|------|---------|----------|
| project_id | string | — | yes |
| github_org | string | REPLACE | yes |
| github_repo | string | REPLACE | yes |
| prod_github_environment | string | `deploy-prod` | no |
| region | string | europe-west2 | no |
| envs | list(string) | [dev, prod] | no |
| org_slug | string | aop | no |
