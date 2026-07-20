#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
branch="$(git -C "$root" branch --show-current)"
source_sha="$(git -C "$root" rev-parse HEAD)"
target_input="${RELEASE_WORKSPACE:?RELEASE_WORKSPACE is required}"
authoritative_remote="git@gitee.com:leegege/sce-product-odoo.git"

[[ "$branch" =~ ^release/tenant-rc-[a-z0-9._-]+$ ]] || {
  echo "[release.workspace.prepare] release/tenant-rc-* branch required" >&2
  exit 2
}
[[ -z "$(git -C "$root" status --short)" ]] || {
  echo "[release.workspace.prepare] source worktree must be clean" >&2
  exit 2
}

workspace_parent="$(cd "$(dirname "$target_input")" && pwd)"
workspace="$workspace_parent/$(basename "$target_input")"
[[ "$workspace" != "$root" ]] || {
  echo "[release.workspace.prepare] target cannot be the source repository" >&2
  exit 2
}
[[ ! -e "$workspace" ]] || {
  echo "[release.workspace.prepare] target already exists" >&2
  exit 2
}

# --no-local prevents hard-linking or borrowing objects from the development
# repository. A single-branch clone also excludes unrelated remote-tracking
# refs, which is required by the release-local history hygiene gate.
git clone --quiet --no-local --single-branch --branch "$branch" "$root" "$workspace"
git -C "$workspace" remote set-url origin "$authoritative_remote"

[[ "$(git -C "$workspace" rev-parse HEAD)" == "$source_sha" ]] || {
  echo "[release.workspace.prepare] cloned SHA mismatch" >&2
  exit 1
}
[[ -z "$(git -C "$workspace" status --short)" ]] || {
  echo "[release.workspace.prepare] cloned worktree is not clean" >&2
  exit 1
}
python3 "$workspace/scripts/verify/repository_clean_history_guard.py" \
  --root "$workspace" --local-hygiene

printf '[release.workspace.prepare] PASS workspace=%s source_sha=%s\n' "$workspace" "$source_sha"
