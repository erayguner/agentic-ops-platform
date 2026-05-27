variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west2"
}

variable "essential_contacts_email" {
  type    = string
  default = "sre-oncall@example.com"
}
