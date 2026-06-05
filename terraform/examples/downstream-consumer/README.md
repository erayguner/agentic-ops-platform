# example/downstream-consumer

Consume the AOP framework from a separate repository. Demonstrates the
recommended pattern:

1. Pin the framework version via `aop_framework_version`.
2. Maintain isolated remote state (`backend.tf`).
3. Author your own variables that map onto `module "aop"` inputs.
4. Add downstream-side IAM after the framework outputs are known.

```bash
cp backend.tf.example backend.tf      # configure your GCS bucket
$EDITOR backend.tf
terraform init
terraform plan \
  -var="project_id=$PROJECT_ID" \
  -var="essential_contacts_email=team-oncall@example.com" \
  -var="slack_auth_token=$SLACK_AUTH_TOKEN" \
  -var="slack_workspace_id=$SLACK_WORKSPACE_ID"
```

## Upgrading the framework

Terraform requires `source = "..."` to be a literal string, so bumping the
framework version is a **two-line edit** in this directory:

1. Update `?ref=v0.5.0` → the next release tag in `main.tf` (release-please auto-bumps it via the `x-release-please-version` marker).
2. Update the default for `aop_framework_version` in `variables.tf` so the
   output stays accurate.

Then:

```bash
terraform plan
```

Use the framework's CHANGELOG to read the diff before bumping.
