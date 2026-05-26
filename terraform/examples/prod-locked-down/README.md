# example/prod-locked-down

The hardened, production-grade composition. The module's `check` blocks
enforce these invariants — this example just supplies the matching inputs:

- `env = "prod"`
- `deletion_policy_prevent = true`
- `min_instance_count_broker >= 1`
- pinned container images (digest references recommended in CI)
- dataset-scoped FinOps billing IAM
- `workflows_invoker_resource_pattern` set to `aop-` so the workflows.invoker
  binding is fenced to AOP-managed workflows only
- Memory Bank-enabled orchestrator (beta)

```bash
cd terraform/examples/prod-locked-down
terraform init
terraform plan \
  -var-file=prod.tfvars \
  -var="slack_auth_token=$SLACK_AUTH_TOKEN"
```

Use a remote backend; apply only through CI with WIF — never from a laptop.
