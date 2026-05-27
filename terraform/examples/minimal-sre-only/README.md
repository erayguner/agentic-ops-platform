# example/minimal-sre-only

Deploys ONLY the SRE agent with a 15-minute Cloud Scheduler sweep, plus the
mandatory eventing + governance layers it depends on. Useful for:

- a single-team adoption that just wants reliability signals
- a sandbox where you don't yet have a Slack workspace wired
- bench-marking the per-agent baseline cost

Nothing else is provisioned — no action broker, no Slack notifier, no
observability. The composition module's `check` blocks pass because we are
in `env = "dev"`.

```bash
cd terraform/examples/minimal-sre-only
terraform init
terraform plan -var="project_id=$PROJECT_ID"
```
