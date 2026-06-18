# example/staging

Production-like deployment of the platform with deletion still allowed. Use
this as the canonical staging environment to exercise:

- warm Cloud Run pools (`min_instance_count >= 1`)
- the daily FinOps schedule
- dataset-scoped billing IAM (set `finops_billing_export_bq_dataset_id`)

```bash
cd terraform/examples/staging
terraform init
terraform plan \
  -var="project_id=$PROJECT_ID" \
  -var="slack_auth_token=$SLACK_AUTH_TOKEN" \
  -var="slack_workspace_id=$SLACK_WORKSPACE_ID" \
  -var="finops_billing_export_bq_dataset_id=billing_export"
```
