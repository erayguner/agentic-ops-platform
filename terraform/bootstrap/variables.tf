variable "project_id" {
  type        = string
  description = "GCP project ID that hosts the Terraform state buckets and WIF resources."
}

variable "region" {
  type        = string
  description = "GCP region for KMS keyrings."
  default     = "europe-west2"
}

variable "org_id" {
  type        = string
  description = "GCP organisation ID. Required for WIF pool — leave empty if no org exists yet."
  default     = ""
}

variable "github_org" {
  type        = string
  description = "GitHub organisation or username that owns the CI repo (for WIF principal set)."
  default     = "REPLACE_GITHUB_ORG"

  validation {
    condition     = var.github_org != "REPLACE_GITHUB_ORG"
    error_message = "github_org must be set to the actual GitHub organisation. The placeholder must not be left in place — WIF will trust the wrong principal."
  }
}

variable "github_repo" {
  type        = string
  description = "GitHub repository name (without org prefix) for WIF principal set."
  default     = "REPLACE_REPO_NAME"

  validation {
    condition     = var.github_repo != "REPLACE_REPO_NAME"
    error_message = "github_repo must be set to the actual GitHub repository name."
  }
}

variable "prod_github_environment" {
  type        = string
  description = <<-EOT
    Name of the GitHub Actions environment that gates prod Terraform applies.
    The prod runner service account (sa-tf-runner-prod) is impersonatable
    ONLY from a workflow run that declares this environment in
    `jobs.<id>.environment.name`. Configure the GitHub environment with
    required reviewers, deployment branch restrictions, and wait-timer to
    enforce a manual approval step before any prod apply.
  EOT
  default     = "deploy-prod"

  validation {
    condition     = length(var.prod_github_environment) > 0
    error_message = "prod_github_environment must be a non-empty string."
  }
}

variable "envs" {
  type        = list(string)
  description = "List of environment names to create state buckets and runner SAs for."
  default     = ["dev", "prod"]

  validation {
    condition     = alltrue([for e in var.envs : contains(["dev", "prod"], e)])
    error_message = "envs must be a subset of [\"dev\", \"prod\"]. Add new environments by extending this validation."
  }
}

variable "org_slug" {
  type        = string
  description = "Short organisation slug used in state bucket names (e.g. 'aop')."
  default     = "aop"
}
