# example/full-dev

Wire every component of the platform in a dev project. Mirrors what the
canonical `terraform/environments/dev/` produces but consumes the new
`aop-platform` composition module instead of stitching modules by hand.

```bash
cd terraform/examples/full-dev
terraform init
terraform plan \
  -var="project_id=$PROJECT_ID" \
  -var="slack_auth_token=$SLACK_AUTH_TOKEN" \
  -var="slack_workspace_id=$SLACK_WORKSPACE_ID"
```

This example does NOT configure a remote backend. Either add a `backend.tf`
or run pre-flight first (`./scripts/preflight.sh full-dev`) to confirm
state-backend readiness.
