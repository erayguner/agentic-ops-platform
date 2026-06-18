# Bootstrap — one-time, hand-run module.
# Creates:
#   - GCS state buckets (one per env) with versioning and CMEK
#   - KMS keyrings and keys for state bucket CMEK
#   - Workload Identity Federation pool and GitHub Actions provider
#   - sa-tf-runner-<env> service accounts (WIF-bound; no keys)
#
# State for this module lives locally (no remote backend block).
# After apply, subsequent modules use the remote GCS backends this creates.
# See README.md for the move-state procedure.

locals {
  # Map env → state bucket name.
  state_buckets = {
    for env in var.envs : env => "${var.org_slug}-tfstate-${env}"
  }

  # Map env → KMS key name
  kms_keys = {
    for env in var.envs : env => "aop-tfstate-${env}-key"
  }
}

# ---------------------------------------------------------------------------
# Enable required APIs
# ---------------------------------------------------------------------------

resource "google_project_service" "kms" {
  project            = var.project_id
  service            = "cloudkms.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  project            = var.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam_credentials" {
  project            = var.project_id
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# KMS — one keyring per env, one key per keyring for state bucket CMEK
# ---------------------------------------------------------------------------

resource "google_kms_key_ring" "tfstate" {
  for_each = toset(var.envs)

  project  = var.project_id
  name     = "aop-tfstate-${each.key}-keyring"
  location = var.region

  depends_on = [google_project_service.kms]
}

resource "google_kms_crypto_key" "tfstate" {
  for_each = toset(var.envs)

  name            = local.kms_keys[each.key]
  key_ring        = google_kms_key_ring.tfstate[each.key].id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

# Grant Cloud Storage service agent permission to use CMEK keys
resource "google_kms_crypto_key_iam_member" "gcs_cmek" {
  for_each = toset(var.envs)

  crypto_key_id = google_kms_crypto_key.tfstate[each.key].id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.project.number}@gs-project-accounts.iam.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}

# ---------------------------------------------------------------------------
# GCS state buckets — one per env, versioning + CMEK
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "tfstate" {
  # checkov:skip=CKV_GCP_62: access logging is redundant with Cloud Audit Logs Data Access logging for this single-purpose Terraform state store.
  for_each = toset(var.envs)

  project       = var.project_id
  name          = local.state_buckets[each.key]
  location      = "EU"
  force_destroy = false

  # State holds resource metadata and secret references — never public.
  public_access_prevention = "enforced"

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.tfstate[each.key].id
  }

  uniform_bucket_level_access = true

  labels = {
    app        = "aop"
    env        = each.key
    component  = "bootstrap"
    managed_by = "terraform"
  }

  depends_on = [google_kms_crypto_key_iam_member.gcs_cmek]
}

# ---------------------------------------------------------------------------
# Workload Identity Federation — one pool per project, one GitHub provider
# ---------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "ci" {
  project                   = var.project_id
  workload_identity_pool_id = "aop-ci-pool"
  display_name              = "AOP CI Workload Identity Pool"
  description               = "WIF pool for GitHub Actions CI/CD; no SA keys required."

  depends_on = [google_project_service.iam]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  # checkov:skip=CKV_GCP_125: trust is fenced by assertion.repository (this org/repo) + ref/event_name/environment in attribute_condition below (GitHub's recommended pattern); CKV_GCP_125 only recognises an assertion.sub claim:value constraint, which is equivalent-or-weaker here.
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.ci.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions OIDC"
  description                        = "GitHub Actions OIDC provider for AOP Terraform CI. Tight scoping by repository + ref + environment (see attribute_condition)."

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  # Attribute mapping — `attribute.environment` and `attribute.ref` are the
  # additional dimensions the per-env principalSet bindings rely on (below).
  # `attribute.event_name` is mapped so future bindings can fence by event
  # type (e.g. `push` vs `pull_request`) without re-touching the provider.
  attribute_mapping = {
    "google.subject"        = "assertion.sub"
    "attribute.actor"       = "assertion.actor"
    "attribute.repository"  = "assertion.repository"
    "attribute.ref"         = "assertion.ref"
    "attribute.environment" = "assertion.environment"
    "attribute.event_name"  = "assertion.event_name"
  }

  # Repository fence first. Then narrow the surface to:
  #   - pushes to refs/heads/main (default branch) — dev applies
  #   - pull_request events — dev planning runs
  #   - any run declaring a GitHub Actions environment — prod via deploy-prod
  # This excludes pushes to arbitrary feature branches without a PR or env.
  attribute_condition = <<-EOT
    assertion.repository == "${var.github_org}/${var.github_repo}"
    && (
      assertion.ref == "refs/heads/main"
      || assertion.event_name == "pull_request"
      || assertion.environment != ""
    )
  EOT
}

# ---------------------------------------------------------------------------
# Terraform runner SAs — one per env (WIF-bound; no exported keys)
# ---------------------------------------------------------------------------

resource "google_service_account" "tf_runner" {
  for_each = toset(var.envs)

  project      = var.project_id
  account_id   = "sa-tf-runner-${each.key}"
  display_name = "AOP Terraform Runner — ${each.key}"
  description  = "CI identity for terraform apply in ${each.key}. Authenticated via WIF; no exported keys."
}

# ---------------------------------------------------------------------------
# WIF principal-set bindings — per-environment, tightly scoped.
#
# Dev runner: impersonatable from any workflow run that passes the provider's
#   attribute_condition (push to main, PR event, or runs declaring an
#   environment). This is intentionally permissive enough for PR-driven
#   plan + dev apply flows.
#
# Prod runner: impersonatable ONLY from runs that declare the
#   `${var.prod_github_environment}` GitHub Actions environment. That
#   environment carries the manual reviewer + branch restriction +
#   wait-timer controls configured in the GitHub UI. A PR build cannot
#   reach the prod SA; only a workflow that explicitly opts into the
#   prod environment (and is gated by the reviewer rule) can.
# ---------------------------------------------------------------------------

resource "google_service_account_iam_member" "wif_tf_runner_dev" {
  count = contains(var.envs, "dev") ? 1 : 0

  service_account_id = google_service_account.tf_runner["dev"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.ci.name}/attribute.repository/${var.github_org}/${var.github_repo}"
}

resource "google_service_account_iam_member" "wif_tf_runner_prod" {
  count = contains(var.envs, "prod") ? 1 : 0

  service_account_id = google_service_account.tf_runner["prod"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.ci.name}/attribute.environment/${var.prod_github_environment}"
}

# ---------------------------------------------------------------------------
# Runner SA state-bucket access — roles/storage.objectAdmin (NOT storage.admin)
#
# storage.objectAdmin grants exactly the create/get/list/update/delete-of-
# objects permissions Terraform's GCS backend (with native locking on
# Terraform >= 1.10) requires. It does NOT grant bucket-level admin (delete
# bucket, set bucket IAM, change retention) — the runner cannot destroy or
# unlock the state bucket itself.
# ---------------------------------------------------------------------------

resource "google_storage_bucket_iam_member" "tf_runner_state_bucket" {
  for_each = toset(var.envs)

  bucket = google_storage_bucket.tfstate[each.key].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.tf_runner[each.key].email}"
}
