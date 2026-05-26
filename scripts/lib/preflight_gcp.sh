# preflight_gcp.sh — gcloud / GCP-flavoured pre-flight checks.
# shellcheck shell=bash

if [[ -n "${AOP_PREFLIGHT_GCP_LOADED:-}" ]]; then
  return 0
fi
readonly AOP_PREFLIGHT_GCP_LOADED=1

# Required APIs for the AOP framework.
AOP_REQUIRED_APIS=(
  aiplatform.googleapis.com
  artifactregistry.googleapis.com
  bigquery.googleapis.com
  cloudkms.googleapis.com
  cloudresourcemanager.googleapis.com
  cloudscheduler.googleapis.com
  compute.googleapis.com
  essentialcontacts.googleapis.com
  eventarc.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  logging.googleapis.com
  modelarmor.googleapis.com
  monitoring.googleapis.com
  pubsub.googleapis.com
  run.googleapis.com
  secretmanager.googleapis.com
  securitycenter.googleapis.com
  storage.googleapis.com
)

aop::check_gcloud_installed() {
  if command -v gcloud >/dev/null 2>&1; then
    aop::pass "gcloud installed ($(gcloud version --format='value(Google Cloud SDK)' 2>/dev/null | head -n1))"
  else
    aop::fail "gcloud CLI not found — install Cloud SDK or set AOP_SKIP_GCLOUD=1"
  fi
}

aop::check_gcloud_adc() {
  if ! command -v gcloud >/dev/null 2>&1; then
    return 0
  fi
  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    aop::pass "Application Default Credentials are valid"
  else
    aop::fail "ADC not available — run 'gcloud auth application-default login' or rely on WIF in CI"
  fi
}

aop::check_gcloud_project_exists() {
  local project_id="$1"
  if [[ -z "${project_id}" ]]; then
    aop::warn "project_id not resolved; skipping project-existence check"
    return 0
  fi
  if gcloud projects describe "${project_id}" --format='value(projectId)' >/dev/null 2>&1; then
    aop::pass "GCP project '${project_id}' exists and is accessible"
  else
    aop::fail "GCP project '${project_id}' is missing OR caller lacks resourcemanager.projects.get"
  fi
}

aop::check_required_apis() {
  local project_id="$1"
  if [[ -z "${project_id}" ]]; then
    aop::warn "project_id not resolved; skipping required-APIs check"
    return 0
  fi

  local enabled
  enabled="$(gcloud services list --enabled --project "${project_id}" \
              --format='value(config.name)' 2>/dev/null || true)"
  if [[ -z "${enabled}" ]]; then
    aop::warn "could not list enabled services for ${project_id} (insufficient permissions?)"
    return 0
  fi

  local missing=()
  local api
  for api in "${AOP_REQUIRED_APIS[@]}"; do
    if ! grep -Fxq "${api}" <<< "${enabled}"; then
      missing+=("${api}")
    fi
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    aop::pass "all ${#AOP_REQUIRED_APIS[@]} required APIs enabled on ${project_id}"
  else
    aop::warn "${#missing[@]} required APIs not yet enabled on ${project_id}: $(printf '%s ' "${missing[@]}")"
    aop::log "→ enable with: gcloud services enable --project ${project_id} $(printf '%s ' "${missing[@]}")"
  fi
}

aop::check_org_policies() {
  local project_id="$1"
  if [[ -z "${project_id}" ]]; then
    return 0
  fi

  if ! gcloud org-policies list --project "${project_id}" --format='value(constraint)' >/dev/null 2>&1; then
    aop::warn "cannot list org policies (orgpolicy.policy.list missing) — skipping policy check"
    return 0
  fi

  local active
  active="$(gcloud org-policies list --project "${project_id}" --format='value(constraint)' 2>/dev/null)"
  if grep -q '^constraints/iam.disableServiceAccountKeyCreation$' <<< "${active}"; then
    aop::pass "iam.disableServiceAccountKeyCreation is active — SA key creation is blocked"
  else
    aop::warn "iam.disableServiceAccountKeyCreation NOT enforced on ${project_id}; AOP requires it in prod"
  fi

  if grep -q '^constraints/gcp.resourceLocations$' <<< "${active}"; then
    aop::pass "gcp.resourceLocations active — region restriction in place"
  else
    aop::warn "gcp.resourceLocations not active; data residency relies solely on Terraform-supplied region"
  fi
}
