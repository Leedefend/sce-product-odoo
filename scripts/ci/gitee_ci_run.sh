#!/usr/bin/env bash
set -euo pipefail

sha="${1:-}"
hook_name="${2:-}"
pr_number="${3:-}"

case "${sha}" in
  (*[!0-9a-f]*|'') echo "[gitee_ci] invalid sha" >&2; exit 2 ;;
esac
if [ "${#sha}" -ne 40 ]; then
  echo "[gitee_ci] invalid sha length" >&2
  exit 2
fi
case "${hook_name}" in
  push_hooks|merge_request_hooks) ;;
  (*) echo "[gitee_ci] unsupported hook" >&2; exit 2 ;;
esac
if [ -n "${pr_number}" ] && ! [[ "${pr_number}" =~ ^[1-9][0-9]*$ ]]; then
  echo "[gitee_ci] invalid pull request number" >&2
  exit 2
fi

readonly repo_url="git@gitee.com:leegege/sce-product-odoo.git"
readonly workspace_root="${GITEE_CI_WORKSPACE_ROOT:-/var/lib/gitee-ci/workspaces}"
readonly artifact_root="${GITEE_CI_ARTIFACT_ROOT:-/var/lib/gitee-ci/artifacts}"
readonly mirror_source_repo="${GITEE_MIRROR_SOURCE_REPO:-}"
mkdir -p "${workspace_root}" "${artifact_root}/${sha}"
workdir="$(mktemp -d "${workspace_root}/job-${sha:0:12}-XXXXXX")"

cleanup() {
  case "${workdir}" in
    ("${workspace_root}"/job-*) rm -rf -- "${workdir}" ;;
    (*) echo "[gitee_ci] cleanup scope rejected" >&2 ;;
  esac
}
trap cleanup EXIT

echo "[gitee_ci] start sha=${sha} event=${hook_name} pr=${pr_number:-none}"
export GIT_TERMINAL_PROMPT=0
export ENV=test
export CI=1

git clone --no-tags "${repo_url}" "${workdir}/repo"
cd "${workdir}/repo"
if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then
  git fetch --no-tags origin "${sha}"
fi
test "$(git rev-parse "${sha}^{commit}")" = "${sha}"
git checkout --detach "${sha}"
test "$(git rev-parse HEAD)" = "${sha}"

python3 -m py_compile \
  scripts/verify/repository_clean_history_guard.py \
  scripts/verify/test_repository_clean_history_guard.py \
  scripts/verify/github_actions_security_guard.py \
  scripts/verify/test_github_actions_security_guard.py
python3 scripts/verify/test_repository_clean_history_guard.py
python3 scripts/verify/test_github_actions_security_guard.py
make verify.repository.clean_history
python3 scripts/verify/clean_product_release_scan.py \
  --report "${artifact_root}/${sha}/clean-product-release-scan.json"
python3 scripts/verify/github_actions_security_guard.py

professional_result="SKIPPED"
if [ "${hook_name}" = "merge_request_hooks" ]; then
  echo "[gitee_ci] professional gate start sha=${sha}"
  pnpm --dir frontend/apps/web install --frozen-lockfile=false
  make ci
  professional_result="PASS"
  echo "[gitee_ci] professional gate PASS sha=${sha}"
fi

printf '%s\n' \
  "SHA=${sha}" \
  "EVENT=${hook_name}" \
  "PR=${pr_number:-none}" \
  "PUBLIC_GUARD=PASS" \
  "PROFESSIONAL_QUALITY_GATE=${professional_result}" \
  "RESULT=PASS" \
  > "${artifact_root}/${sha}/result.txt"

# Publish only a verified Gitee main commit to the credential-free local handoff.
# The separate mirror service owns the GitHub write key and is the only process
# able to push this object to GitHub.
if [ "${hook_name}" = "push_hooks" ] && [ -n "${mirror_source_repo}" ]; then
  remote_main_sha="$(git ls-remote origin refs/heads/main | awk 'NR == 1 {print $1}')"
  if [ "${remote_main_sha}" = "${sha}" ]; then
    git push "${mirror_source_repo}" \
      "${sha}:refs/heads/main"
    echo "[gitee_ci] mirror handoff PASS sha=${sha}"
  else
    echo "[gitee_ci] mirror handoff SKIPPED reason=not_gitee_main"
  fi
fi
echo "[gitee_ci] PASS sha=${sha}"
