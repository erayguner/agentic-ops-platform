# preflight_state.sh — Terraform state backend pre-flight checks.
# shellcheck shell=bash

if [[ -n "${AOP_PREFLIGHT_STATE_LOADED:-}" ]]; then
  return 0
fi
readonly AOP_PREFLIGHT_STATE_LOADED=1

aop::check_state_bucket_for_env() {
  local project_id="$1"
  local env="$2"
  if [[ -z "${project_id}" || -z "${env}" ]]; then
    return 0
  fi

  local bucket="${AOP_ORG_SLUG:-aop}-tfstate-${env}"

  if ! gcloud storage buckets describe "gs://${bucket}" \
      --format='value(name)' >/dev/null 2>&1; then
    aop::fail "state bucket gs://${bucket} not found — run terraform/bootstrap first"
    return 0
  fi

  aop::pass "state bucket gs://${bucket} exists"

  # Versioning + CMEK + UBLA flags.
  local versioning
  versioning="$(gcloud storage buckets describe "gs://${bucket}" \
                --format='value(versioning_enabled)' 2>/dev/null || echo "")"
  if [[ "${versioning}" == "True" || "${versioning}" == "true" ]]; then
    aop::pass "state bucket has versioning enabled"
  else
    aop::fail "state bucket gs://${bucket} does NOT have versioning enabled"
  fi

  local ubla
  ubla="$(gcloud storage buckets describe "gs://${bucket}" \
          --format='value(iam_config.uniform_bucket_level_access.enabled)' 2>/dev/null || echo "")"
  if [[ "${ubla}" == "True" || "${ubla}" == "true" ]]; then
    aop::pass "state bucket has uniform bucket-level access"
  else
    aop::warn "state bucket gs://${bucket} is missing uniform bucket-level access"
  fi
}
