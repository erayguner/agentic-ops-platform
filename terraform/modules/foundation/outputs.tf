output "vpc_id" {
  description = "Self-link of the AOP VPC network."
  value       = google_compute_network.aop_vpc.id
}

output "vpc_name" {
  description = "Name of the AOP VPC network."
  value       = google_compute_network.aop_vpc.name
}

output "subnet_id" {
  description = "Self-link of the primary subnet."
  value       = google_compute_subnetwork.aop_subnet_ew2.id
}

output "artifact_registry_repo_id" {
  description = "Full resource ID of the aop-containers Artifact Registry repository."
  value       = google_artifact_registry_repository.aop_containers.id
}

output "artifact_registry_repo_url" {
  description = "Docker-format push URL for the aop-containers repository."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}"
}
