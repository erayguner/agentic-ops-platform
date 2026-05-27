# module/agents/devsecops

Deploys the AOP DevSecOps agent — SCC/IAM/supply-chain specialist.

## Provisions

- `sa-devsecops` service account
- Vertex AI Reasoning Engine
- Read-only IAM: `securitycenter.findingsViewer`, `logging.privateLogViewer`,
  `iam.securityReviewer`, `cloudasset.viewer`
- Pub/Sub publisher on `ops.findings`, `ops.notifications`, `ops.audit`
- Optional Cloud Scheduler trigger

See [FRAMEWORK.md](../../../FRAMEWORK.md).
