# module/agents/sre

Deploys the AOP SRE agent — reliability/latency/error-rate specialist.

## Provisions

- `sa-sre` service account
- Vertex AI Reasoning Engine
- Read-only IAM: `logging.viewer`, `monitoring.viewer`, `cloudtrace.user`,
  `errorreporting.viewer`, `run.viewer`, `container.viewer`
- Pub/Sub publisher on `ops.findings`, `ops.notifications`, `ops.audit`
- Optional Cloud Scheduler trigger

See the top-level [FRAMEWORK.md](../../../FRAMEWORK.md) for adoption guidance.
