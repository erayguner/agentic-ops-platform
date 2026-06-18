# Per-module tflint config. The `terraform_unused_declarations` rule is
# disabled because billing_account / org_id / folder_id are part of the
# module's public interface (callers pass them via the composition module
# and the legacy env roots) even though this module body does not yet
# reference every value internally.

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_unused_declarations" {
  enabled = false
}
