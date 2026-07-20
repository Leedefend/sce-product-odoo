#!/usr/bin/env bash
set -euo pipefail

readonly source_repo="${GITEE_MIRROR_SOURCE_REPO:-/var/lib/gitee-mirror/source.git}"
readonly github_repo="Leedefend/sce-product-odoo"
readonly github_url="git@github.com:${github_repo}.git"
readonly key_file="${GITHUB_MIRROR_KEY_FILE:-/etc/gitee-mirror/github_ed25519}"
readonly known_hosts="${GITHUB_MIRROR_KNOWN_HOSTS:-/etc/gitee-mirror/github_known_hosts}"
readonly expected_source="leegege/sce-product-odoo"
readonly configured_source="${GITEE_MIRROR_SOURCE_REPOSITORY:-${expected_source}}"

[ "${configured_source}" = "${expected_source}" ] || {
  echo "[gitee_github_mirror] BLOCKED source_repository_not_allowed" >&2
  exit 2
}
[ -d "${source_repo}" ] && [ -f "${key_file}" ] && [ -f "${known_hosts}" ] || {
  echo "[gitee_github_mirror] BLOCKED required_path_missing" >&2
  exit 2
}

candidate_sha="$(git -c safe.directory="${source_repo}" --git-dir="${source_repo}" rev-parse refs/heads/main)"
case "${candidate_sha}" in
  (*[!0-9a-f]*|'') echo "[gitee_github_mirror] BLOCKED invalid_candidate_sha" >&2; exit 2 ;;
esac
[ "${#candidate_sha}" -eq 40 ] || {
  echo "[gitee_github_mirror] BLOCKED invalid_candidate_sha_length" >&2
  exit 2
}
git -c safe.directory="${source_repo}" --git-dir="${source_repo}" cat-file -e "${candidate_sha}^{commit}"

export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="ssh -i ${key_file} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=${known_hosts}"
github_sha="$(git ls-remote "${github_url}" refs/heads/main | awk 'NR == 1 {print $1}')"
case "${github_sha}" in
  (*[!0-9a-f]*|'') echo "[gitee_github_mirror] BLOCKED invalid_github_main_sha" >&2; exit 2 ;;
esac

if [ "${github_sha}" = "${candidate_sha}" ]; then
  printf '[gitee_github_mirror] PASS sha=%s mode=already_aligned\n' "${candidate_sha}"
  exit 0
fi
git -c safe.directory="${source_repo}" --git-dir="${source_repo}" cat-file -e "${github_sha}^{commit}" || {
  echo "[gitee_github_mirror] BLOCKED github_main_missing_from_source" >&2
  exit 2
}
git -c safe.directory="${source_repo}" --git-dir="${source_repo}" merge-base --is-ancestor \
  "${github_sha}" "${candidate_sha}" || {
  echo "[gitee_github_mirror] BLOCKED non_fast_forward" >&2
  exit 2
}

# Deliberately push the immutable commit ID, never a caller-controlled ref.
git -c safe.directory="${source_repo}" --git-dir="${source_repo}" push "${github_url}" \
  "${candidate_sha}:refs/heads/main"
post_sha="$(git ls-remote "${github_url}" refs/heads/main | awk 'NR == 1 {print $1}')"
[ "${post_sha}" = "${candidate_sha}" ] || {
  echo "[gitee_github_mirror] BLOCKED post_push_sha_mismatch" >&2
  exit 2
}
printf '[gitee_github_mirror] PASS sha=%s mode=fast_forward_only\n' "${candidate_sha}"
