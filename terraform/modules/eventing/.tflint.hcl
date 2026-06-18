# Per-module tflint config. Disables `terraform_unused_declarations` because
# slack_notifier_url is part of the public interface (the env roots use it
# to wire the Eventarc trigger destination on second apply) and the
# scaffolding locals `dlq_topics` / `schema_topics` are kept for future
# generation logic.

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_unused_declarations" {
  enabled = false
}
