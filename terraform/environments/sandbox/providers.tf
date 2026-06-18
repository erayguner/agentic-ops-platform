provider "google" {
  project = var.project_id
  region  = var.region

  # User ADC has no default quota project; route the quota/billing header for
  # APIs that require one (e.g. essentialcontacts.googleapis.com) to the target
  # project. TF-native fix for the "API requires a quota project" 403 seen under
  # user Application Default Credentials.
  user_project_override = true
  billing_project       = var.project_id

  default_labels = {
    app        = "aop"
    env        = "dev"
    managed_by = "terraform"
    purpose    = "tf-deploy-validation"
  }
}

provider "google-beta" {
  project = var.project_id
  region  = var.region

  user_project_override = true
  billing_project       = var.project_id

  default_labels = {
    app        = "aop"
    env        = "dev"
    managed_by = "terraform"
    purpose    = "tf-deploy-validation"
  }
}
