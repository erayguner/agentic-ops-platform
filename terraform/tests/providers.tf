# Dummy provider config for `terraform test` — no real cloud calls are made;
# tests run in plan-only mode and assert on plan output / variable validation.

provider "google" {
  project                         = "test-project"
  region                          = "europe-west2"
  user_project_override           = false
  billing_project                 = "test-project"
  request_timeout                 = "5s"
  add_terraform_attribution_label = false
}

provider "google-beta" {
  project                         = "test-project"
  region                          = "europe-west2"
  user_project_override           = false
  billing_project                 = "test-project"
  request_timeout                 = "5s"
  add_terraform_attribution_label = false
}
