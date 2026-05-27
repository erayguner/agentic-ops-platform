# preflight_common.sh — shared helpers for AOP pre-flight checks.
# Sourced by scripts/preflight.sh; not intended to be executed standalone.
# shellcheck shell=bash

if [[ -n "${AOP_PREFLIGHT_COMMON_LOADED:-}" ]]; then
  return 0
fi
readonly AOP_PREFLIGHT_COMMON_LOADED=1

# Colour codes only when stdout is a tty.
if [[ -t 1 ]]; then
  readonly AOP_COL_RED=$'\033[31m'
  readonly AOP_COL_GREEN=$'\033[32m'
  readonly AOP_COL_YELLOW=$'\033[33m'
  readonly AOP_COL_CYAN=$'\033[36m'
  readonly AOP_COL_BOLD=$'\033[1m'
  readonly AOP_COL_RESET=$'\033[0m'
else
  readonly AOP_COL_RED=""
  readonly AOP_COL_GREEN=""
  readonly AOP_COL_YELLOW=""
  readonly AOP_COL_CYAN=""
  readonly AOP_COL_BOLD=""
  readonly AOP_COL_RESET=""
fi

AOP_PASS_COUNT=0
AOP_FAIL_COUNT=0
AOP_WARN_COUNT=0
AOP_FAIL_MESSAGES=()

aop::header() {
  printf '\n%s%s== %s ==%s\n' "${AOP_COL_BOLD}" "${AOP_COL_CYAN}" "$*" "${AOP_COL_RESET}"
}

aop::log() {
  printf '  %s\n' "$*"
}

aop::pass() {
  AOP_PASS_COUNT=$((AOP_PASS_COUNT + 1))
  printf '  %s[PASS]%s %s\n' "${AOP_COL_GREEN}" "${AOP_COL_RESET}" "$*"
}

aop::warn() {
  AOP_WARN_COUNT=$((AOP_WARN_COUNT + 1))
  printf '  %s[WARN]%s %s\n' "${AOP_COL_YELLOW}" "${AOP_COL_RESET}" "$*"
}

aop::fail() {
  AOP_FAIL_COUNT=$((AOP_FAIL_COUNT + 1))
  AOP_FAIL_MESSAGES+=("$*")
  printf '  %s[FAIL]%s %s\n' "${AOP_COL_RED}" "${AOP_COL_RESET}" "$*"
}

aop::summary() {
  printf '\n%sSummary:%s pass=%d warn=%d fail=%d\n' \
    "${AOP_COL_BOLD}" "${AOP_COL_RESET}" \
    "${AOP_PASS_COUNT}" "${AOP_WARN_COUNT}" "${AOP_FAIL_COUNT}"

  if [[ "${AOP_FAIL_COUNT}" -gt 0 ]]; then
    printf '\n%sFailures:%s\n' "${AOP_COL_RED}" "${AOP_COL_RESET}"
    for msg in "${AOP_FAIL_MESSAGES[@]}"; do
      printf '  - %s\n' "${msg}"
    done
    exit 1
  fi

  printf '\n%sAll pre-flight checks passed.%s\n' "${AOP_COL_GREEN}" "${AOP_COL_RESET}"
}

aop::check_tool() {
  local tool="$1"
  local required="${2:-required}"
  if command -v "${tool}" >/dev/null 2>&1; then
    aop::pass "${tool} present"
    return 0
  fi
  if [[ "${required}" == "optional" ]]; then
    aop::warn "${tool} not on PATH (optional)"
  else
    aop::fail "required tool '${tool}' not on PATH"
  fi
}

# Extract a tfvar value from a .tfvars or .auto.tfvars file under the target.
# Falls back to the supplied default. We deliberately do not eval; values
# are returned as-is (quotes stripped).
aop::extract_tfvar() {
  local dir="$1"
  local key="$2"
  local default="${3:-}"
  local value=""

  shopt -s nullglob
  for f in "${dir}"/*.tfvars "${dir}"/*.auto.tfvars; do
    [[ -f "${f}" ]] || continue
    # Match: key = "value"  OR  key = value (no quotes).
    value="$(awk -v k="${key}" '
      $1 == k && $2 == "=" {
        sub(/^[^=]*=[ \t]*/, "", $0)
        gsub(/^"|"$/, "", $0)
        print
        exit
      }' "${f}")"
    if [[ -n "${value}" ]]; then
      printf '%s' "${value}"
      return 0
    fi
  done
  shopt -u nullglob

  printf '%s' "${default}"
}

aop::run_terraform_fmt_check() {
  local dir="$1"
  if terraform -chdir="${dir}" fmt -check -recursive >/dev/null 2>&1; then
    aop::pass "terraform fmt clean under ${dir}"
  else
    aop::fail "terraform fmt -recursive reported diffs in ${dir}"
  fi
}

aop::run_terraform_init_validate() {
  local dir="$1"
  if terraform -chdir="${dir}" init -backend=false -input=false >/dev/null 2>&1; then
    if terraform -chdir="${dir}" validate >/dev/null 2>&1; then
      aop::pass "terraform validate clean for ${dir}"
    else
      aop::fail "terraform validate failed for ${dir}"
    fi
  else
    aop::fail "terraform init failed for ${dir}"
  fi
}

aop::run_tflint() {
  local dir="$1"
  if tflint --chdir="${dir}" --minimum-failure-severity=error >/dev/null 2>&1; then
    aop::pass "tflint clean for ${dir}"
  else
    aop::warn "tflint reported findings for ${dir} (severity >= error)"
  fi
}

aop::run_trivy_iac() {
  local dir="$1"
  if trivy config --severity HIGH,CRITICAL --exit-code 0 "${dir}" >/dev/null 2>&1; then
    aop::pass "trivy IaC scan clean for ${dir}"
  else
    aop::warn "trivy reported HIGH/CRITICAL misconfig in ${dir}"
  fi
}

aop::run_checkov() {
  local dir="$1"
  if checkov -d "${dir}" --quiet --compact >/dev/null 2>&1; then
    aop::pass "checkov clean for ${dir}"
  else
    aop::warn "checkov reported findings in ${dir}"
  fi
}
