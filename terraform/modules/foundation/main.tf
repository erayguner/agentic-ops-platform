locals {
  common_labels = merge(
    {
      app        = "aop"
      env        = var.env
      component  = "foundation"
      managed_by = "terraform"
    },
    var.labels,
  )
}

# ---------------------------------------------------------------------------
# Essential Contacts
# ---------------------------------------------------------------------------

resource "google_essential_contacts_contact" "security" {
  parent                              = "projects/${var.project_id}"
  email                               = var.essential_contacts_email
  language_tag                        = var.essential_contacts_language
  notification_category_subscriptions = ["SECURITY"]
}

resource "google_essential_contacts_contact" "billing" {
  parent                              = "projects/${var.project_id}"
  email                               = var.essential_contacts_email
  language_tag                        = var.essential_contacts_language
  notification_category_subscriptions = ["BILLING"]
}

resource "google_essential_contacts_contact" "technical" {
  parent                              = "projects/${var.project_id}"
  email                               = var.essential_contacts_email
  language_tag                        = var.essential_contacts_language
  notification_category_subscriptions = ["TECHNICAL"]
}

# ---------------------------------------------------------------------------
# Artifact Registry — aop-containers
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "aop_containers" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repo
  description   = "AOP container images (agents, broker, notifier)"
  format        = "DOCKER"

  labels = local.common_labels
}

# ---------------------------------------------------------------------------
# Custom-mode VPC + subnet
# ---------------------------------------------------------------------------

resource "google_compute_network" "aop_vpc" {
  project                 = var.project_id
  name                    = var.vpc_name
  auto_create_subnetworks = false
  description             = "AOP baseline custom-mode VPC"
}

resource "google_compute_subnetwork" "aop_subnet_ew2" {
  project                  = var.project_id
  name                     = var.subnet_name
  region                   = var.region
  network                  = google_compute_network.aop_vpc.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# ---------------------------------------------------------------------------
# Firewall — deny all ingress by default; allow only RFC-1918 internal
# ---------------------------------------------------------------------------

resource "google_compute_firewall" "deny_all_ingress" {
  project     = var.project_id
  name        = "${var.vpc_name}-deny-all-ingress"
  network     = google_compute_network.aop_vpc.name
  direction   = "INGRESS"
  priority    = 65534
  description = "Default-deny all ingress; overridden by specific allow rules."

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
}

resource "google_compute_firewall" "allow_internal_ingress" {
  project     = var.project_id
  name        = "${var.vpc_name}-allow-internal-ingress"
  network     = google_compute_network.aop_vpc.name
  direction   = "INGRESS"
  priority    = 1000
  description = "Allow RFC-1918 internal traffic within the VPC."

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
}

# ---------------------------------------------------------------------------
# Enable required APIs
# ---------------------------------------------------------------------------

locals {
  required_apis = [
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "essentialcontacts.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "eventarc.googleapis.com",
    "bigquery.googleapis.com",
    "securitycenter.googleapis.com",
    "modelarmor.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project                    = var.project_id
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}
