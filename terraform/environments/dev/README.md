# environments/dev

Dev root module for the AOP Terraform configuration. Composes all seven AOP modules against the `ops-agents-dev` project.

## Prerequisites

1. Bootstrap has been run: `aop-tfstate-dev` GCS bucket and `sa-tf-runner-dev` SA exist.
2. `ops-agents-dev` GCP project exists with billing enabled.
3. CI has WIF credentials configured (output of bootstrap).

## Init / Plan / Apply

```bash
cd terraform/environments/dev

# Init — downloads providers, configures GCS backend
terraform init

# Plan — review changes
terraform plan -var-file=terraform.tfvars

# Apply — CI runs this via sa-tf-runner-dev / WIF
terraform apply -var-file=terraform.tfvars
```

## Sensitive variables

Do NOT set `slack_auth_token` in `terraform.tfvars`. Inject it via CI:

```bash
terraform apply \
  -var-file=terraform.tfvars \
  -var="slack_auth_token=$SLACK_AUTH_TOKEN"
```

## Dev vs prod differences

| Aspect | Dev |
|--------|-----|
| `deletion_policy_prevent` | false — reasoning engines can be destroyed |
| `min_instance_count` (broker, notifier) | 0 — scale to zero |
| Container images | `:latest` tags acceptable |
| Org Policy | recommendations only (project scope) |

## Destroy

`terraform destroy` is allowed in dev. Protected by the GCS state lock, not by `deletion_policy`.
