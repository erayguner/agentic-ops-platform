provider "google" {
  project = var.project_id
  region  = var.region

  default_labels = {
    app        = "aop"
    env        = "staging"
    managed_by = "terraform"
  }
}

provider "google-beta" {
  project = var.project_id
  region  = var.region

  default_labels = {
    app        = "aop"
    env        = "staging"
    managed_by = "terraform"
  }
}
