# gcloud / non-Terraform commands

Every step in the deploy/destroy lifecycle that is **not** performed by
Terraform, with the reason, exact command, expected result, and whether it must
be manually reversed. The goal is "Terraform for everything supported; gcloud
only where Terraform cannot or for an unavoidable one-off."

There are exactly **two** classes of non-Terraform action: building container
images (Terraform cannot build containers) and cleaning up non-Terraform
side-effects after destroy.

---

## 1. Build + push container images (required, pre-`apply`)

**Reason:** Terraform cannot build OCI images. The two Cloud Run services need
real images in Artifact Registry before the full `apply` (Cloud Run validates
the image at deploy). Run after `terraform apply -target=module.foundation`
(which creates the `aop-containers` repo and enables `cloudbuild`).

**Command:**
```bash
AR="europe-west2-docker.pkg.dev/agentic-ops-platform/aop-containers"
gcloud builds submit services/slack-notifier \
  --config=services/cloudbuild.yaml \
  --substitutions=_IMAGE="$AR/slack-notifier:latest" --region=europe-west2
gcloud builds submit services/action-broker \
  --config=services/cloudbuild.yaml \
  --substitutions=_IMAGE="$AR/action-broker:latest" --region=europe-west2
```
`services/cloudbuild.yaml` builds with `DOCKER_BUILDKIT=1` (the Dockerfiles use
BuildKit `--mount` cache; the `gcloud builds submit --tag` shortcut uses a
non-BuildKit builder and fails — finding from the chronicle).

**Expected:** two builds `SUCCESS`; `slack-notifier:latest` and
`action-broker:latest` present in Artifact Registry.

**Manual reversal needed?** No for the images (they live in the TF-managed
Artifact Registry repo and are deleted when `terraform destroy` removes the
repo). **Yes** for the staging bucket — see §3.

---

## 2. ADC quota project — handled in Terraform (no gcloud needed)

**Reason:** user Application Default Credentials have no quota project, so
`essentialcontacts.googleapis.com` (and some others) return 403 "requires a
quota project" (finding F12).

**How it is handled:** in Terraform, not gcloud —
`provider "google" { user_project_override = true; billing_project = project_id }`.

**Alternative one-off (NOT used here):** if you prefer the gcloud route,
`gcloud auth application-default set-quota-project agentic-ops-platform`
(reversal: `gcloud auth application-default set-quota-project <other>` or unset).
We avoided it to keep the fix in code/repeatable.

---

## 3. Post-destroy residual cleanup (teardown)

`terraform destroy` removes all Terraform-managed resources. Two residuals are
created **outside** Terraform and are cleaned up manually:

### 3a. Cloud Build staging bucket
**Reason:** `gcloud builds submit` auto-creates `gs://<project>_cloudbuild` for
source staging; it is not Terraform-managed.
```bash
gcloud storage rm --recursive gs://agentic-ops-platform_cloudbuild --quiet
```
**Expected:** bucket and contents removed. **Reversal:** none (recreated
automatically on the next build).

### 3b. Default VPC network (auto-created by enabling Compute API)
**Reason:** enabling `compute.googleapis.com` auto-creates a `default` auto-mode
VPC + `default-allow-{icmp,internal,ssh,rdp}` firewall rules. These are not
Terraform-managed and (the open SSH/RDP rules) are mild security residue.
```bash
gcloud compute firewall-rules delete \
  default-allow-icmp default-allow-internal default-allow-rdp default-allow-ssh \
  --project=agentic-ops-platform --quiet
gcloud compute networks delete default --project=agentic-ops-platform --quiet
```
**Expected:** 0 networks, 0 firewall rules remaining.
**Reversal (if ever needed):** `gcloud compute networks create default --subnet-mode=auto`.

---

## 4. Read-only discovery (non-mutating; for the record)

Used during review; change nothing, need no reversal:
`gcloud projects describe`, `gcloud billing projects describe`,
`gcloud organizations list`, `gcloud services list`,
`gcloud run/pubsub/secrets/... list`, `bq ls`, `terraform plan/validate`.

---

## Summary

| Action | Tool | Reversal |
|--------|------|----------|
| Build/push 2 images | `gcloud builds submit` | images via `terraform destroy`; bucket §3a |
| ADC quota project | **Terraform** (`user_project_override`) | n/a |
| Enable APIs | **Terraform** (`google_project_service`) | `gcloud services disable` (optional) |
| Remove Cloud Build bucket | `gcloud storage rm` | recreated on next build |
| Remove default VPC | `gcloud compute …delete` | `gcloud compute networks create default` |
| Everything else (108-resource platform) | **Terraform** | `terraform destroy` |
