output "state_bucket_names" {
  description = "Map of env → GCS state bucket name."
  value       = { for env, bucket in google_storage_bucket.tfstate : env => bucket.name }
}

output "wif_pool_name" {
  description = "Full resource name of the Workload Identity Federation pool."
  value       = google_iam_workload_identity_pool.ci.name
}

output "wif_provider_name" {
  description = "Full resource name of the GitHub Actions WIF provider."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "tf_runner_sa_emails" {
  description = "Map of env → Terraform runner SA email."
  value       = { for env, sa in google_service_account.tf_runner : env => sa.email }
}

output "kms_key_ids" {
  description = "Map of env → KMS crypto key ID used for state bucket CMEK."
  value       = { for env, key in google_kms_crypto_key.tfstate : env => key.id }
}
