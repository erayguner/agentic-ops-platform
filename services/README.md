# Services — Agentic Operations Platform

Two Cloud Run services form the human-facing and execution control plane.

## slack-notifier

Receives `OpsNotification v1` from `ops.notifications`, renders Slack Block Kit
messages per the §6.6 contract, and handles interactivity (Approve / Reject
buttons → `ops.actions.approved`).

- Default dry-run mode: `LIVE_SLACK_ENABLED=false` — logs Block Kit JSON.
- See [slack-notifier/README.md](slack-notifier/README.md) for env vars and channel routing.

## action-broker

Custom MCP server exposing five tools (`propose_action`, `request_approval`,
`execute`, `rollback`, `status`). The only writer on GCP — all agent write
actions go through this service under policy control and short-lived
per-action-class SA impersonation.

- Default dry-run mode: `LIVE_MODE=false` — executors raise `NotImplementedError`;
  event chain (Pub/Sub, audit, idempotency) runs in log-only mode.
- See [action-broker/README.md](action-broker/README.md) for security model.

## Quick compile check

```bash
cd /path/to/agentic-ops-platform
python3 -m compileall -q services/
```

## Key contracts

| Thing                | Source of truth                                                                      |
| -------------------- | ------------------------------------------------------------------------------------ |
| Topic names          | `terraform/modules/eventing/main.tf`                                                 |
| Schema field names   | `agents/aop_common/schemas.py`, `services/*/schemas.py`                              |
| Action-class strings | `services/action-broker/policy/action_classes.yaml`                                  |
| SA names             | `terraform/modules/agent-runtime/main.tf`, `terraform/modules/action-broker/main.tf` |
| Slack channels       | `services/slack-notifier/blockkit.py`                                                |
| Block Kit layout     | `docs/DESIGN-REVIEW.md §6.6`                                                         |
