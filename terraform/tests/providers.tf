# Provider config for `terraform test`.
#
# Tests use `command = plan` and never make real API calls; the access_token
# below is a literal so the provider does NOT attempt to load Application
# Default Credentials (ADC). This keeps the suite self-contained in CI where
# no GCP credentials are available.
#
# IMPORTANT: every `run` block must pass these providers explicitly because
# `module { source = ... }` blocks create an isolated root and do NOT inherit
# the test directory's providers automatically.

provider "google" {
  project      = "test-project"
  region       = "europe-west2"
  access_token = "fake-token-plan-only-never-used-against-the-api"
}

provider "google-beta" {
  project      = "test-project"
  region       = "europe-west2"
  access_token = "fake-token-plan-only-never-used-against-the-api"
}
