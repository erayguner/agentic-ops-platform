# AOP dev environment — placeholder values
# Replace all REPLACE_* values before running terraform apply.
# NEVER commit real secrets (slack_auth_token) to version control.

project_id               = "ops-agents-dev"
region                   = "europe-west2"
essential_contacts_email = "platform-owner@example.com"

# org_id and folder_id: leave empty until a GCP org is established
org_id    = ""
folder_id = ""

# Slack — populate via CI secret injection
# slack_auth_token = "xoxb-..."   # do not commit
slack_auth_token_version = "1"
slack_workspace_id       = "REPLACE_WITH_WORKSPACE_ID"

slack_channel_incidents = "#ops-incidents"
slack_channel_security  = "#ops-security"
slack_channel_finops    = "#ops-finops"
slack_channel_platform  = "#ops-platform"

# Container images — set after first CI build
container_image_slack_notifier = "europe-west2-docker.pkg.dev/ops-agents-dev/aop-containers/slack-notifier:latest"
container_image_action_broker  = "europe-west2-docker.pkg.dev/ops-agents-dev/aop-containers/action-broker:latest"
