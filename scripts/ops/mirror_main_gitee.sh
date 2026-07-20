#!/usr/bin/env bash
set -euo pipefail

branch="$(git branch --show-current)"
[[ "$branch" == "main" ]] || { echo "[mirror.main.gitee] BLOCKED current_branch_must_be_main" >&2; exit 2; }
[[ -z "$(git status --porcelain)" ]] || { echo "[mirror.main.gitee] BLOCKED worktree_not_clean" >&2; exit 2; }
git remote get-url origin >/dev/null
git remote get-url gitee >/dev/null
git fetch --prune origin main
git fetch --prune gitee main
local_sha="$(git rev-parse refs/heads/main)"
origin_sha="$(git rev-parse refs/remotes/origin/main)"
gitee_sha="$(git rev-parse refs/remotes/gitee/main)"
[[ "$local_sha" == "$origin_sha" ]] || { echo "[mirror.main.gitee] BLOCKED local_main_not_origin_main" >&2; exit 2; }
git merge-base --is-ancestor "$gitee_sha" "$origin_sha" || {
  echo "[mirror.main.gitee] BLOCKED gitee_main_not_fast_forward_ancestor" >&2
  exit 2
}
if [[ "$gitee_sha" != "$origin_sha" ]]; then
  git push gitee refs/heads/main:refs/heads/main
fi
remote_sha="$(git ls-remote gitee refs/heads/main | awk 'NR == 1 {print $1}')"
[[ "$remote_sha" == "$origin_sha" ]] || { echo "[mirror.main.gitee] BLOCKED post_push_sha_mismatch" >&2; exit 2; }
printf '[mirror.main.gitee] PASS sha=%s mode=fast_forward_only\n' "$origin_sha"
