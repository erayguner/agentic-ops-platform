variable "project_id" {
  type        = string
  description = "GCP project ID where foundation resources are created."
}

variable "region" {
  type        = string
  description = "Default GCP region."
  default     = "europe-west2"
}

variable "env" {
  type        = string
  description = "Environment name (dev|staging|prod)."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be 'dev', 'staging', or 'prod'."
  }
}

variable "billing_account" {
  type        = string
  description = "Billing account ID to associate with the project (e.g. 'XXXXXX-XXXXXX-XXXXXX')."
  default     = ""
}

variable "org_id" {
  type        = string
  description = "GCP organisation ID. Leave empty when running without an org resource — controls that require org scope will be skipped."
  default     = ""
}

variable "folder_id" {
  type        = string
  description = "GCP folder ID. Leave empty when no folder hierarchy exists — essential contacts and some org policies will degrade to project scope."
  default     = ""
}

variable "essential_contacts_email" {
  type        = string
  description = "Email address for essential contacts (security, billing, legal, product, technical)."
}

variable "essential_contacts_language" {
  type        = string
  description = "Language code for essential-contacts notifications."
  default     = "en"
}

variable "vpc_name" {
  type        = string
  description = "Name of the baseline custom-mode VPC."
  default     = "aop-vpc"
}

variable "subnet_name" {
  type        = string
  description = "Name of the primary subnet."
  default     = "aop-subnet-ew2"
}

variable "subnet_cidr" {
  type        = string
  description = "CIDR range for the primary subnet."
  default     = "10.10.0.0/24"
}

variable "artifact_registry_repo" {
  type        = string
  description = "Artifact Registry repository name for AOP container images."
  default     = "aop-containers"
}

variable "labels" {
  type        = map(string)
  description = "Additional labels to merge with the standard AOP label set."
  default     = {}
}
