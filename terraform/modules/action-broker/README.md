# module/action-broker

Provisions the Action Broker Cloud Run service — the single write execution choke point for the AOP.

## Security model

The broker is the **only** component that holds write grants. It holds no broad write IAM itself. Instead:

1. `sa-action-broker` has `roles/iam.serviceAccountTokenCreator` on each per-action-class SA.
2. The broker generates a short-lived token for the relevant action SA, executes the write, then discards the token.
3. This constrains the blast radius of a compromised broker: it can only execute the specific actions for which per-action SAs exist.

**Never** create `google_service_account_key` resources for these SAs.

## Resources created

- **`sa-action-broker`** — broker Cloud Run identity. Holds NO broad write IAM.
- **7 per-action-class SAs** — `sa-action-cloudrun-scale`, `sa-action-cloudrun-rollback`, `sa-action-iam-disable-key`, `sa-action-secret-disable`, `sa-action-scc-mute`, `sa-action-workflows-run`, `sa-action-terraform-plan`.
- **3 custom IAM roles** — narrower than the closest predefined role:
  - `aopIamServiceAccountKeyDisableOnly` (replaces `roles/iam.serviceAccountKeyAdmin`) — only `iam.serviceAccountKeys.disable/get/list`. NO `create`. NO `delete`.
  - `aopSecretVersionDisableOnly` (replaces `roles/secretmanager.admin`) — only `secretmanager.versions.disable/get/list` + `secretmanager.secrets.get/list`. NO create, delete, or setIamPolicy.
  - `aopSccFindingMuteOnly` (replaces `roles/securitycenter.findingsEditor`) — only `securitycenter.findings.setMute/get/list`. NO `update`. NO `setState`.
- **Predefined role grants** where no narrower alternative gives the executor what it needs: `roles/run.developer` (scale + rollback executors), `roles/workflows.invoker` (with optional resource-pattern IAM condition via `var.workflows_invoker_resource_pattern`), `roles/viewer` (terraform.plan — read-only by definition).
- **`iam.serviceAccountTokenCreator`** grants from `sa-action-broker` to each action SA — the broker's only write-like permission, the foundation of the short-lived-token impersonation pattern.
- **`google_cloud_run_v2_service`** — `action-broker` service with `ingress = INTERNAL_LOAD_BALANCER` and authenticated invocation. An explicit `run.invoker` allow-list is composed (self-grant for the Pub/Sub OIDC push path, plus optional agent SA emails passed via `var.agent_sa_emails` — typically wired from the env-root, not from this module).
- **Secret** — `broker-policy-key` for policy engine signing key.
- **Pub/Sub push subscription** — `ops.actions.approved.broker-push`.

## Inputs

| Name                               | Type         | Default     | Required |
| ---------------------------------- | ------------ | ----------- | -------- |
| project_id                         | string       | —           | yes      |
| env                                | string       | —           | yes      |
| ops_actions_approved_topic_id      | string       | —           | yes      |
| ops_actions_requested_topic_id     | string       | —           | yes      |
| ops_actions_executed_topic_id      | string       | —           | yes      |
| ops_audit_topic_id                 | string       | —           | yes      |
| container_image                    | string       | placeholder | no       |
| min_instance_count                 | number       | 0           | no       |
| max_instance_count                 | number       | 3           | no       |
| agent_sa_emails                    | list(string) | `[]`        | no       |
| workflows_invoker_resource_pattern | string       | `""`        | no       |

## Outputs

Broker service URL and all SA emails. See `outputs.tf`.
