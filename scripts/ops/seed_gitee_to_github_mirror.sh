#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
[[ "${branch}" =~ ^(feature|fix|refactor|audit|release|codex)/.+$ ]] || {
  echo "[gitee_mirror_seed] denied branch=${branch}" >&2
  exit 2
}
sha="${GITEE_MIRROR_SEED_SHA:-}"
case "${sha}" in
  (*[!0-9a-f]*|'') echo "[gitee_mirror_seed] invalid sha" >&2; exit 2 ;;
esac
[ "${#sha}" -eq 40 ] || { echo "[gitee_mirror_seed] invalid sha length" >&2; exit 2; }
[ "${GITEE_MIRROR_SEED_CONFIRM:-}" = "1" ] || {
  echo "[gitee_mirror_seed] GITEE_MIRROR_SEED_CONFIRM=1 is required" >&2
  exit 2
}

readonly target="root@1.95.2.123"
remote_line="$(ssh -o BatchMode=yes "${target}" \
  "runuser -u gitee-ci -- env GIT_SSH_COMMAND='/usr/bin/ssh -i /etc/gitee-ci/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/etc/gitee-ci/known_hosts' git ls-remote git@gitee.com:leegege/sce-product-odoo.git refs/heads/main")"
remote_main="${remote_line%%[[:space:]]*}"
[ "${remote_main}" = "${sha}" ] || {
  echo "[gitee_mirror_seed] BLOCKED requested_sha_not_gitee_main" >&2
  exit 2
}
ssh -o BatchMode=yes "${target}" \
  "systemd-run --quiet --wait --pipe --collect --unit=gitee-mirror-seed --uid=gitee-ci --gid=gitee-ci --property=SupplementaryGroups=gitee-mirror-source --property=EnvironmentFile=/etc/gitee-ci/sce-product-odoo-worker.env /opt/gitee-ci/sce-product-odoo/gitee_ci_run.sh '${sha}' push_hooks ''"
echo "[gitee_mirror_seed] PASS sha=${sha}"
