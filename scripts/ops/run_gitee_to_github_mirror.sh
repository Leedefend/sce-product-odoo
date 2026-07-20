#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
[[ "${branch}" =~ ^(feature|fix|refactor|audit|release|codex)/.+$ ]] || {
  echo "[gitee_mirror_run] denied branch=${branch}" >&2
  exit 2
}
[ "${GITEE_MIRROR_RUN_CONFIRM:-}" = "1" ] || {
  echo "[gitee_mirror_run] GITEE_MIRROR_RUN_CONFIRM=1 is required" >&2
  exit 2
}
readonly target="root@1.95.2.123"
ssh -o BatchMode=yes "${target}" 'set -e; systemctl start gitee-to-github-mirror.service; systemctl show gitee-to-github-mirror.service --property=Result --property=ExecMainStatus --value | grep -qx "success\|0"; systemctl start gitee-to-github-mirror.timer'
echo "[gitee_mirror_run] PASS"
