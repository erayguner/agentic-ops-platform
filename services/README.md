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
`execute`, `rollback`, `status`).  The only writer on GCP — all agent write
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

| Thing | Source of truth |
|---|---|
| Topic names | `INTERFACE-CONTRACT.md §3` |
| Schema field names | `INTERFACE-CONTRACT.md §4` |
| Action-class strings | `INTERFACE-CONTRACT.md §5` |
| SA names | `INTERFACE-CONTRACT.md §2` |
| Slack channels | `INTERFACE-CONTRACT.md §1` |
| Block Kit layout | `docs/DESIGN-REVIEW.md §6.6` |
