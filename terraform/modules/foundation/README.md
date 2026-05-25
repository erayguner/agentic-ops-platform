# module/foundation

Establishes the baseline GCP project infrastructure for the AOP:

- **Essential Contacts** — security, billing, and technical notification contacts.
- **Artifact Registry** — `aop-containers` Docker repository for all AOP container images.
- **Custom-mode VPC** — `aop-vpc` with one subnet in `europe-west2`, Private Google Access enabled, VPC Flow Logs on.
- **Firewall** — default-deny ingress; RFC-1918 internal allow.
- **API enablement** — all GCP services required by the AOP modules.

## Degraded mode (no org/folder)

When `org_id` and `folder_id` are both empty, org-scoped resources (Essential Contacts at folder/org level, Org Policy) are skipped; contacts and policies default to project scope. The `foundation` module itself always applies at project scope.

## Usage

```hcl
module "foundation" {
  source = "../../modules/foundation"

  project_id               = "ops-agents-dev"
  env                      = "dev"
  essential_contacts_email = "platform-owner@example.com"
}
```

## Inputs

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| project_id | string | — | yes | GCP project ID |
| env | string | — | yes | dev or prod |
| essential_contacts_email | string | — | yes | Contact email |
| region | string | europe-west2 | no | GCP region |
| org_id | string | "" | no | GCP org ID |
| folder_id | string | "" | no | GCP folder ID |
| vpc_name | string | aop-vpc | no | VPC name |
| subnet_name | string | aop-subnet-ew2 | no | Subnet name |
| subnet_cidr | string | 10.10.0.0/24 | no | Subnet CIDR |
| artifact_registry_repo | string | aop-containers | no | AR repo name |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | VPC self-link |
| vpc_name | VPC name |
| subnet_id | Subnet self-link |
| artifact_registry_repo_id | AR repository resource ID |
| artifact_registry_repo_url | Docker push URL |
