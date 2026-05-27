# preflight_naming.sh — naming/region/env consistency checks.
# shellcheck shell=bash

if [[ -n "${AOP_PREFLIGHT_NAMING_LOADED:-}" ]]; then
  return 0
fi
readonly AOP_PREFLIGHT_NAMING_LOADED=1

aop::check_naming_project_id() {
  local project_id="$1"
  if [[ -z "${project_id}" ]]; then
    aop::warn "project_id not resolved; skipping naming check"
    return 0
  fi
  if [[ "${project_id}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]]; then
    aop::pass "project_id '${project_id}' matches naming convention"
  else
    aop::fail "project_id '${project_id}' violates GCP naming rules (6-30 chars, lowercase)"
  fi
  if [[ "${project_id}" == *"REPLACE"* ]]; then
    aop::fail "project_id contains a placeholder ('${project_id}') — substitute before deploying"
  fi
}

aop::check_naming_region() {
  local region="$1"
  if [[ -z "${region}" ]]; then
    return 0
  fi
  if [[ "${region}" =~ ^[a-z]+-[a-z]+[0-9]+$ ]]; then
    aop::pass "region '${region}' looks like a GCP region"
  else
    aop::fail "region '${region}' does not look like a GCP region (e.g. 'europe-west2')"
  fi
  if [[ "${region}" != europe-* ]]; then
    aop::warn "region '${region}' is not in the EU — review data-residency constraints"
  fi
}

aop::check_naming_env() {
  local env="$1"
  case "${env}" in
    dev|staging|prod)
      aop::pass "env '${env}' is recognised by the framework"
      ;;
    *)
      aop::fail "env '${env}' must be one of dev / staging / prod"
      ;;
  esac
}
