#!/usr/bin/env bash
set -euo pipefail

[ "${GITHUB_MIRROR_RULESET_CONFIRM:-}" = "1" ] || {
  echo "[github_mirror_ruleset] GITHUB_MIRROR_RULESET_CONFIRM=1 is required" >&2
  exit 2
}
readonly repository="Leedefend/sce-product-odoo"
readonly key_title="sce-gitee-to-github-mirror"
readonly ruleset_name="main-gitee-authoritative-mirror"
readonly public_key_file="${GITHUB_MIRROR_PUBLIC_KEY_FILE:-}"

other_write_keys="$(gh api "repos/${repository}/keys" --jq ".[] | select(.read_only == false and .title != \"${key_title}\") | .id")"
[ -z "${other_write_keys}" ] || {
  echo "[github_mirror_ruleset] BLOCKED unexpected_write_deploy_key" >&2
  exit 2
}

existing_key_id="$(gh api "repos/${repository}/keys" --jq ".[] | select(.title == \"${key_title}\") | .id" | head -1)"
if [ -z "${existing_key_id}" ]; then
  if [ -n "${public_key_file}" ]; then
    test -s "${public_key_file}"
    public_key="$(cat "${public_key_file}")"
  else
    public_key="$(ssh -o BatchMode=yes root@1.95.2.123 'cat /etc/gitee-mirror/github_ed25519.pub')"
  fi
  existing_key_id="$(gh api --method POST "repos/${repository}/keys" \
    -f title="${key_title}" -f key="${public_key}" -F read_only=false --jq .id)"
fi
test -n "${existing_key_id}"
write_key_count="$(gh api "repos/${repository}/keys" --jq '[.[] | select(.read_only == false)] | length')"
[ "${write_key_count}" = "1" ] || {
  echo "[github_mirror_ruleset] BLOCKED write_deploy_key_count" >&2
  exit 2
}

payload="$(mktemp)"
trap 'rm -f -- "${payload}"' EXIT
jq -n --arg name "${ruleset_name}" '{
  name: $name,
  target: "branch",
  enforcement: "active",
  bypass_actors: [{actor_id: null, actor_type: "DeployKey", bypass_mode: "always"}],
  conditions: {ref_name: {include: ["refs/heads/main"], exclude: []}},
  rules: [
    {type: "deletion"},
    {type: "non_fast_forward"},
    {type: "pull_request", parameters: {
      dismiss_stale_reviews_on_push: true,
      require_code_owner_review: false,
      require_last_push_approval: false,
      required_approving_review_count: 0,
      required_review_thread_resolution: true,
      allowed_merge_methods: ["squash", "rebase"]
    }},
    {type: "required_status_checks", parameters: {
      do_not_enforce_on_create: false,
      strict_required_status_checks_policy: true,
      required_status_checks: [
        {context: "public_guard"},
        {context: "professional_authorization"},
        {context: "professional_quality_gate"}
      ]
    }}
  ]
}' > "${payload}"

ruleset_id="$(gh api "repos/${repository}/rulesets" --jq ".[] | select(.name == \"${ruleset_name}\") | .id" | head -1)"
if [ -n "${ruleset_id}" ]; then
  gh api --method PUT "repos/${repository}/rulesets/${ruleset_id}" --input "${payload}" >/dev/null
else
  ruleset_id="$(gh api --method POST "repos/${repository}/rulesets" --input "${payload}" --jq .id)"
fi

gh api "repos/${repository}/rulesets/${ruleset_id}" --jq \
  'select(.enforcement == "active") | select(any(.bypass_actors[]; .actor_type == "DeployKey" and .bypass_mode == "always")) | .id' \
  | grep -qx "${ruleset_id}"

# Classic protection layers with rulesets. Remove it only after the active
# replacement has been read back and verified.
if gh api "repos/${repository}/branches/main/protection" >/dev/null 2>&1; then
  gh api --method DELETE "repos/${repository}/branches/main/protection" >/dev/null
fi
echo "[github_mirror_ruleset] PASS ruleset_id=${ruleset_id} deploy_key_id=${existing_key_id}"
