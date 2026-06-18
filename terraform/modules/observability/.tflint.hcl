# Per-module tflint config. Disables `terraform_unused_declarations` because
# region / slack_channel_security / slack_workspace_id are part of the
# public interface (callers in env roots and the composition module pass
# them in) even though the current monitoring resources don't reference
# every value internally.

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_unused_declarations" {
  enabled = false
}
