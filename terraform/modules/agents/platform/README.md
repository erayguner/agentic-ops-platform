# module/agents/platform

Deploys the AOP Platform Engineering agent — drift/deploy-health specialist.

## Provisions

- `sa-platform` service account
- Vertex AI Reasoning Engine
- Read-only IAM: `cloudasset.viewer`, `resourcemanager.projectViewer`,
  `cloudbuild.builds.viewer`, `clouddeploy.viewer`
- Pub/Sub publisher on `ops.findings`, `ops.notifications`, `ops.audit`
- Optional Cloud Scheduler trigger

See [FRAMEWORK.md](../../../FRAMEWORK.md).
