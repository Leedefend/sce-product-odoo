#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
[[ "${branch}" =~ ^(feature|fix|refactor|audit|release|codex)/.+$ ]] || {
  echo "[gitee_mirror_install] denied branch=${branch}" >&2
  exit 2
}
[ "${GITEE_MIRROR_SERVER_CONFIRM:-}" = "1" ] || {
  echo "[gitee_mirror_install] GITEE_MIRROR_SERVER_CONFIRM=1 is required" >&2
  exit 2
}
readonly target="root@1.95.2.123"
stage="$(ssh -o BatchMode=yes "${target}" 'mktemp -d /tmp/gitee-mirror-install-XXXXXX')"
case "${stage}" in
  (/tmp/gitee-mirror-install-*) ;;
  (*) echo "[gitee_mirror_install] invalid staging path" >&2; exit 2 ;;
esac
cleanup() {
  ssh -o BatchMode=yes "${target}" "rm -rf -- '${stage}'" >/dev/null 2>&1 || true
}
trap cleanup EXIT
tar -cf - \
  scripts/ci/gitee_ci_run.sh \
  scripts/ops/gitee_to_github_mirror.sh \
  deploy/gitee-mirror/install.sh \
  deploy/gitee-mirror/gitee-to-github-mirror.service \
  deploy/gitee-mirror/gitee-to-github-mirror.timer \
  | ssh -o BatchMode=yes "${target}" "tar -xf - -C '${stage}'"
ssh -o BatchMode=yes "${target}" "bash '${stage}/deploy/gitee-mirror/install.sh' '${stage}'"
