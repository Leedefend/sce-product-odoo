#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
if ! [[ "${branch}" =~ ^(feature|fix|refactor|audit|release|codex)/.+$ ]]; then
  echo "[gitee_ci_https] denied branch=${branch}" >&2
  exit 2
fi
if [ "${GITEE_CI_HTTPS_CONFIRM:-}" != "1" ]; then
  echo "[gitee_ci_https] GITEE_CI_HTTPS_CONFIRM=1 is required" >&2
  exit 2
fi

readonly target="root@1.95.2.123"
ssh -o BatchMode=yes "${target}" 'bash -s' < deploy/gitee-ci/install_https.sh
