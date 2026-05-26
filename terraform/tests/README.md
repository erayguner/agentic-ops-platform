# terraform/tests

Native `terraform test` suite. Tests run in plan-only mode (`command = plan`)
so they never touch a real cloud — they assert on Terraform's own validation
machinery and `check` block diagnostics.

Run locally:

```bash
cd terraform/tests
terraform init -backend=false
terraform test
```

The suite verifies:

- `_base` rejects invalid agent slugs.
- `_base` refuses to grant `roles/owner` to an agent SA.
- `aop-platform` rejects unknown env values.
- `aop-platform` rejects unknown agent keys.
- `aop-platform` rejects project IDs that violate GCP naming rules.
- `_base` requires both `cron` and `target_uri` when a schedule is set.

The CI workflow `terraform.yml` runs `terraform test` on every PR.
