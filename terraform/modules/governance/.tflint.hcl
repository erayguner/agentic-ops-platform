# Per-module tflint config. Disables `terraform_unused_declarations` because
# region / audit_bq_table_id are part of the public interface, and the
# locals has_org / has_folder are kept as scaffolding for the org-scoped
# Org Policy resources that are commented-out in main.tf and will be
# activated when an org is bound.

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_unused_declarations" {
  enabled = false
}
