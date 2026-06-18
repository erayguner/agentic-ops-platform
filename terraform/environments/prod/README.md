# environments/prod

Prod root module for the AOP Terraform configuration. Composes all seven AOP modules against the `ops-agents-prod` project.

## Prerequisites

1. Bootstrap has been run: `aop-tfstate-prod` GCS bucket and `sa-tf-runner-prod` SA exist.
2. `ops-agents-prod` GCP project exists with billing enabled.
3. CI has WIF credentials configured (output of bootstrap).
4. **Two-approver review** is required on the GitHub protected `main` branch before merge triggers apply.

## Init / Plan / Apply

```bash
cd terraform/environments/prod

# Init
terraform init

# Plan (CI posts plan JSON to PR and uploads to GCS)
terraform plan -var-file=terraform.tfvars

# Apply — only via CI after two-approver merge gate
terraform apply -var-file=terraform.tfvars
```

## Sensitive variables

`slack_auth_token` must be injected by CI — never in `terraform.tfvars`.

## Prod vs dev differences

| Aspect                                  | Prod                                         |
| --------------------------------------- | -------------------------------------------- |
| `deletion_policy_prevent`               | true — reasoning engines cannot be destroyed |
| `min_instance_count` (broker, notifier) | 1 — always warm                              |
| Container images                        | SHA-pinned tags only (never `:latest`)       |
| `eventing.deletion_policy_prevent`      | true — protects `ops.audit` topic            |
| Two-approver apply                      | enforced via CODEOWNERS + branch protection  |

## Emergency break-glass

If the normal CI path is unavailable, a designated break-glass SA (`sa-tf-emergency`, disabled by default in bootstrap) can be manually enabled by the Platform Owner. All break-glass applies must be documented in the audit ledger within 24h.
