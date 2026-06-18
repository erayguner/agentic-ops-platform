# Per-module tflint config. Disables `terraform_unused_declarations` because
# audit_bq_dataset_id is exposed for cross-module compatibility (callers
# still pass it) and the local.common_labels is kept as scaffolding for
# future label propagation onto agent resources.

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_unused_declarations" {
  enabled = false
}
