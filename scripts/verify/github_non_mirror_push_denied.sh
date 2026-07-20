#!/usr/bin/env bash
set -euo pipefail

readonly repository="Leedefend/sce-product-odoo"
readonly ruleset_name="main-gitee-authoritative-mirror"
ruleset_id="$(gh api "repos/${repository}/rulesets" --jq ".[] | select(.name == \"${ruleset_name}\") | .id" | head -1)"
[ -n "${ruleset_id}" ]

gh api "repos/${repository}/rulesets/${ruleset_id}" --jq '
  select(.enforcement == "active")
  | select(.target == "branch")
  | select(.conditions.ref_name.include == ["refs/heads/main"])
  | select(any(.rules[]; .type == "pull_request"))
  | select(any(.rules[]; .type == "required_status_checks"))
  | select(any(.rules[]; .type == "deletion"))
  | select(any(.rules[]; .type == "non_fast_forward"))
  | select((.bypass_actors | length) == 1)
  | select(.bypass_actors[0].actor_type == "DeployKey")
  | select(.bypass_actors[0].bypass_mode == "always")
  | .id' | grep -qx "${ruleset_id}"

if gh api "repos/${repository}/branches/main/protection" >/dev/null 2>&1; then
  echo "[github_non_mirror_test] BLOCKED classic_protection_still_layered" >&2
  exit 2
fi
write_key_count="$(gh api "repos/${repository}/keys" --jq '[.[] | select(.read_only == false and .title == "sce-gitee-to-github-mirror")] | length')"
[ "${write_key_count}" = "1" ]
echo "[github_non_mirror_test] PASS ordinary_direct_push_denied=true evidence=active_ruleset_readback"
