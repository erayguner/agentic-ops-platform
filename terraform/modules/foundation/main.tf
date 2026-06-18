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

# The Essential Contacts API keys a contact by email and rejects a second
# contact with the same address (409 CONTACT_ALREADY_EXISTS). The previous
# design created three contacts that all shared var.essential_contacts_email,
# which fails whenever the same address covers multiple categories (the common
# case). Consolidate to ONE contact subscribed to all relevant categories.
moved {
  from = google_essential_contacts_contact.security
  to   = google_essential_contacts_contact.primary
}

resource "google_essential_contacts_contact" "primary" {
  parent                              = "projects/${var.project_id}"
  email                               = var.essential_contacts_email
  language_tag                        = var.essential_contacts_language
  notification_category_subscriptions = ["SECURITY", "TECHNICAL", "BILLING"]

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Artifact Registry — aop-containers
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "aop_containers" {
  # checkov:skip=CKV_GCP_84: CMEK is a documented roadmap hardening; Google-managed encryption (AES-256, always-on) is the scaffold baseline. See docs/GOVERNANCE-MAPPING.md §12.
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repo
  description   = "AOP container images (agents, broker, notifier)"
  format        = "DOCKER"

  labels = local.common_labels

  # Wait for artifactregistry.googleapis.com before creating the repo (avoids
  # the "API has not been used in project before" first-apply race).
  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Custom-mode VPC + subnet
# ---------------------------------------------------------------------------

resource "google_compute_network" "aop_vpc" {
  project                 = var.project_id
  name                    = var.vpc_name
  auto_create_subnetworks = false
  description             = "AOP baseline custom-mode VPC"

  # Wait for compute.googleapis.com before creating network resources (subnet
  # and firewalls reference this network, so they inherit the ordering).
  depends_on = [google_project_service.apis]
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
    "cloudbuild.googleapis.com",
    # Backing APIs for the read-only Google Cloud MCP servers the agents consume
    # (observability / diagnostics / RCA / inspection). See docs/deployment/MCP-SERVERS.md.
    "cloudtrace.googleapis.com",
    "clouderrorreporting.googleapis.com",
    "cloudasset.googleapis.com",
    "networkmanagement.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project                    = var.project_id
  service                    = each.key
  disable_on_destroy         = false
  disable_dependent_services = false
}
