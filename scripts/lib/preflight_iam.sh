# preflight_iam.sh — IAM / WIF / Terraform runner SA pre-flight checks.
# shellcheck shell=bash

if [[ -n "${AOP_PREFLIGHT_IAM_LOADED:-}" ]]; then
  return 0
fi
readonly AOP_PREFLIGHT_IAM_LOADED=1

aop::check_wif_pool() {
  local project_id="$1"
  local pool_id="${AOP_WIF_POOL_ID:-aop-ci-pool}"
  if [[ -z "${project_id}" ]]; then
    return 0
  fi
  if gcloud iam workload-identity-pools describe "${pool_id}" \
      --project "${project_id}" --location global \
      --format='value(name)' >/dev/null 2>&1; then
    aop::pass "WIF pool '${pool_id}' exists on ${project_id}"
  else
    aop::warn "WIF pool '${pool_id}' missing on ${project_id} — bootstrap module not applied yet?"
  fi
}

aop::check_tf_runner_sa() {
  local project_id="$1"
  local env="$2"
  local sa="sa-tf-runner-${env}@${project_id}.iam.gserviceaccount.com"

  if [[ -z "${project_id}" || -z "${env}" ]]; then
    return 0
  fi

  if gcloud iam service-accounts describe "${sa}" \
      --project "${project_id}" --format='value(email)' >/dev/null 2>&1; then
    aop::pass "Terraform runner SA '${sa}' exists"
  else
    aop::fail "Terraform runner SA '${sa}' missing — bootstrap module not applied for env=${env}"
    return 0
  fi

  # Spot-check that the runner has the role needed to read the state bucket.
  local bucket="${AOP_ORG_SLUG:-aop}-tfstate-${env}"
  if gcloud storage buckets get-iam-policy "gs://${bucket}" --format=json 2>/dev/null \
      | grep -q "\"serviceAccount:${sa}\""; then
    aop::pass "Runner SA has IAM on state bucket gs://${bucket}"
  else
    aop::warn "Runner SA may not yet hold roles/storage.objectAdmin on gs://${bucket}"
  fi
}

aop::check_required_secrets() {
  local project_id="$1"
  local env="$2"
  if [[ -z "${project_id}" ]]; then
    return 0
  fi

  local required_secrets=(
    "slack-oauth-token"
    "slack-signing-secret"
    "broker-policy-key"
  )

  local existing
  existing="$(gcloud secrets list --project "${project_id}" --format='value(name)' 2>/dev/null || true)"
  if [[ -z "${existing}" ]]; then
    aop::warn "could not list Secret Manager secrets on ${project_id}; skipping"
    return 0
  fi

  local s
  for s in "${required_secrets[@]}"; do
    if grep -Fxq "${s}" <<< "${existing}"; then
      aop::pass "Secret '${s}' exists on ${project_id}"
    elif [[ "${env}" == "prod" ]]; then
      aop::fail "Secret '${s}' missing on ${project_id} (env=prod must be pre-provisioned)"
    else
      aop::warn "Secret '${s}' missing on ${project_id} (env=${env})"
    fi
  done
}
