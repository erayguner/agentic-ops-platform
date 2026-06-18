#!/usr/bin/env bash
# preflight.sh — validate deployment prerequisites for the AOP Terraform
# framework BEFORE running terraform plan / apply. The script returns a
# non-zero exit code if any check fails; CI uses it as a gate.
#
# Usage:
#   scripts/preflight.sh [example_or_env_path]
#
# When called with no argument, the script runs the framework-level checks
# only (provider versions, tflint, terraform fmt). When called with a path
# (e.g. `scripts/preflight.sh terraform/examples/full-dev`), it additionally:
#   - reads variables from the module
#   - resolves project_id / region / env
#   - checks gcloud / ADC auth
#   - checks required APIs
#   - checks state backend bucket
#   - checks runner SA IAM
#   - checks naming conventions on project_id
#   - lints + validates the target
#
# Any check can be skipped via env vars:
#   AOP_SKIP_GCLOUD=1     — skip gcloud-dependent checks
#   AOP_SKIP_TFLINT=1     — skip tflint
#   AOP_SKIP_TRIVY=1      — skip terraform misconfig scanning
#   AOP_SKIP_CHECKOV=1    — skip checkov
#
# Exit codes:
#   0  all checks passed
#   1  one or more checks failed
#   2  invalid usage

set -Euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source helper libraries. shellcheck SC1091 (cannot follow at lint time) is
# acceptable here because the sourced paths are dynamic at runtime.
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/preflight_common.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/preflight_gcp.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/preflight_iam.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/preflight_state.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/preflight_naming.sh"

TARGET="${1:-}"

aop::header "AOP pre-flight — framework-level checks"
aop::check_tool terraform
aop::check_tool tflint
aop::check_tool jq

if [[ -n "${TARGET}" ]]; then
  if [[ ! -d "${TARGET}" ]]; then
    aop::fail "target ${TARGET} is not a directory"
    aop::summary
    exit 2
  fi

  aop::header "AOP pre-flight — module checks (${TARGET})"

  # Always-on Terraform checks.
  aop::run_terraform_fmt_check "${TARGET}"
  aop::run_terraform_init_validate "${TARGET}"

  if [[ "${AOP_SKIP_TFLINT:-0}" != "1" ]]; then
    aop::run_tflint "${TARGET}"
  fi

  if [[ "${AOP_SKIP_TRIVY:-0}" != "1" ]] && command -v trivy >/dev/null 2>&1; then
    aop::run_trivy_iac "${TARGET}"
  fi

  if [[ "${AOP_SKIP_CHECKOV:-0}" != "1" ]] && command -v checkov >/dev/null 2>&1; then
    aop::run_checkov "${TARGET}"
  fi

  # Resolve project_id / region / env from the target's tfvars or defaults.
  PROJECT_ID="$(aop::extract_tfvar "${TARGET}" project_id)"
  REGION="$(aop::extract_tfvar "${TARGET}" region "europe-west2")"
  ENV="$(aop::extract_tfvar "${TARGET}" env "dev")"

  aop::log "Resolved: project_id=${PROJECT_ID:-<unset>} region=${REGION} env=${ENV}"

  aop::check_naming_project_id "${PROJECT_ID}"
  aop::check_naming_region "${REGION}"
  aop::check_naming_env "${ENV}"

  if [[ "${AOP_SKIP_GCLOUD:-0}" != "1" ]] && [[ -n "${PROJECT_ID}" ]]; then
    aop::check_gcloud_installed
    aop::check_gcloud_adc
    aop::check_gcloud_project_exists "${PROJECT_ID}"
    aop::check_required_apis "${PROJECT_ID}"
    aop::check_state_bucket_for_env "${PROJECT_ID}" "${ENV}"
    aop::check_wif_pool "${PROJECT_ID}"
    aop::check_tf_runner_sa "${PROJECT_ID}" "${ENV}"
    aop::check_required_secrets "${PROJECT_ID}" "${ENV}"
    aop::check_org_policies "${PROJECT_ID}"
  fi
fi

aop::summary
