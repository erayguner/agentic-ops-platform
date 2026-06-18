terraform {
  # observability uses the write-only auth_token_wo attribute (provider 7.x),
  # which requires Terraform >= 1.11. Validated on Terraform 1.14.
  required_version = ">= 1.11"

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

  # NO backend block — the sandbox validation root uses LOCAL state on purpose.
  # Rationale: `terraform destroy` then removes 100% of provisioned cloud
  # resources, leaving no state bucket / KMS key residual. The production path
  # uses the GCS backend provisioned by terraform/bootstrap (see
  # docs/deployment/README.md, "State backend strategy").
}
