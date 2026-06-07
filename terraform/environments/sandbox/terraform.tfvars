# Sandbox validation root — COMMITTED PLACEHOLDERS ONLY.
# Contains NO real project IDs, billing accounts, or tokens (repo convention).
# Real values for an actual run live in sandbox.auto.tfvars (gitignored) and
# override these — see README.md.

project_id     = "REPLACE_PROJECT"
project_number = "000000000000"
region         = "europe-west2"

essential_contacts_email = "platform-owner@example.com"

billing_account_id = "REPLACE-BILLING-ACCOUNT"
budget_amount_usd  = 20

container_image_slack_notifier = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/slack-notifier:latest"
container_image_action_broker  = "europe-west2-docker.pkg.dev/REPLACE_PROJECT/aop-containers/action-broker:latest"
