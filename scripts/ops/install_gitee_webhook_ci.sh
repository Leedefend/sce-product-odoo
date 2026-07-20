#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
if ! [[ "${branch}" =~ ^(feature|fix|refactor|audit|release|codex)/.+$ ]]; then
  echo "[gitee_ci_install] denied branch=${branch}" >&2
  exit 2
fi
if [ "${GITEE_CI_SERVER_CONFIRM:-}" != "1" ]; then
  echo "[gitee_ci_install] GITEE_CI_SERVER_CONFIRM=1 is required" >&2
  exit 2
fi

readonly target="root@1.95.2.123"
stage="$(ssh -o BatchMode=yes "${target}" 'mktemp -d /tmp/gitee-ci-install-XXXXXX')"
case "${stage}" in
  (/tmp/gitee-ci-install-*) ;;
  (*) echo "[gitee_ci_install] invalid remote staging path" >&2; exit 2 ;;
esac
cleanup() {
  ssh -o BatchMode=yes "${target}" "rm -rf -- '${stage}'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

tar -cf - \
  scripts/ci/gitee_webhook_ci.py \
  scripts/ci/gitee_ci_run.sh \
  deploy/gitee-ci/gitee-webhook-ci.service \
  deploy/gitee-ci/gitee-ci-worker.service \
  deploy/gitee-ci/install.sh \
  | ssh -o BatchMode=yes "${target}" "tar -xf - -C '${stage}'"
ssh -o BatchMode=yes "${target}" "bash '${stage}/deploy/gitee-ci/install.sh' '${stage}'"
