terraform {
  required_version = ">= 1.10"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.34"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.34"
    }
  }
}
