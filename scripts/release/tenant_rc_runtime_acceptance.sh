#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

image="${CANDIDATE_IMAGE:?CANDIDATE_IMAGE is required}"
expected_digest="${CANDIDATE_IMAGE_DIGEST:?CANDIDATE_IMAGE_DIGEST is required}"
artifacts="$(realpath "${CANDIDATE_ARTIFACTS:?CANDIDATE_ARTIFACTS is required}")/runtime-acceptance"
project="${RC_ACCEPTANCE_PROJECT:-sc-tenant-rc-acceptance}"
database="sc_frontend_acceptance"
frontend_port="${RC_ACCEPTANCE_FRONTEND_PORT:-18188}"
odoo_port="${RC_ACCEPTANCE_ODOO_PORT:-18189}"
source_sha="$(git rev-parse HEAD)"
password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(30))')"

[[ "$project" =~ ^sc-tenant-rc-[a-z0-9-]+$ ]] || { echo "invalid RC acceptance project" >&2; exit 2; }
actual_digest="$(docker image inspect "$image" --format '{{.Id}}')"
[[ "$actual_digest" == "$expected_digest" ]] || { echo "[tenant.rc.runtime] image digest mismatch" >&2; exit 2; }
mkdir -p "$artifacts" "$artifacts/page-identity" "$artifacts/j02-j03" \
  "$artifacts/j04-j06" "$artifacts/j07-j08" "$artifacts/j09-j11" "$artifacts/j12-j13"

compose=(docker compose -p "$project" -f docker-compose.production-candidate.yml -f docker-compose.tenant-rc-acceptance.yml)
export CANDIDATE_IMAGE="$image" CANDIDATE_PROJECT="$project" CANDIDATE_DB="$database"
export CANDIDATE_NGINX_PORT="$frontend_port" CANDIDATE_ODOO_PORT="$odoo_port"

cleanup() { "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
"${compose[@]}" up -d --wait db redis
"${compose[@]}" run --rm --no-deps --entrypoint python3 odoo \
  /usr/local/bin/render_odoo_conf.py /etc/odoo/odoo.conf.template /var/lib/odoo/odoo.conf

product_modules="$(python3 scripts/ops/tenant_module_set.py product)"
"${compose[@]}" run --rm --no-deps -e SC_ENVIRONMENT=acceptance -e SC_ALLOW_DEMO_DATA=1 \
  --entrypoint odoo odoo -c /var/lib/odoo/odoo.conf -d "$database" \
  -i "$product_modules,smart_construction_acceptance_fixture" --without-demo=all \
  --workers=0 --max-cron-threads=0 --no-http --stop-after-init
"${compose[@]}" up -d --wait odoo nginx

odoo_shell() {
  local script="$1"
  "${compose[@]}" exec -T -e SC_ENVIRONMENT=acceptance -e SC_ALLOW_DEMO_DATA=1 \
    -e "SC_ACCEPTANCE_FIXTURE_PASSWORD=$password" odoo \
    odoo shell -d "$database" -c /var/lib/odoo/odoo.conf --log-level=error < "$script"
}
odoo_shell scripts/release/tenant_rc_acceptance_fixture_init.py \
  > "$artifacts/fixture-init.json"
fixture_output="$(odoo_shell scripts/verify/frontend_productization_fixture.py)"
odoo_shell scripts/verify/frontend_productization_fixture_nonfixture_regression.py \
  > "$artifacts/fixture-nonfixture-regression.log"

export FRONTEND_URL="http://127.0.0.1:$frontend_port"
export BASE_URL="$FRONTEND_URL" DB_NAME="$database"
export SC_ACCEPTANCE_FIXTURE_PASSWORD="$password" ROLE_SMOKE_PASSWORD="$password"

export_ids() {
  local script="$1" prefix="$2" line
  while IFS= read -r line; do
    [[ "$line" == "$prefix"* ]] || continue
    export "$line"
  done < <(odoo_shell "$script")
}

export_ids scripts/verify/frontend_productization_fixture_runtime_ids.py FRONTEND_FIXTURE_

export_ids scripts/verify/frontend_page_identity_runtime_metadata.py FRONTEND_PAGE_IDENTITY_ACTION_XMLIDS_JSON=
AUDIT_ROLES=fixture_role_finance,fixture_role_project_a_member,fixture_role_pm,fixture_role_owner \
  ARTIFACTS_DIR="$artifacts/page-identity" \
  node frontend/apps/web/scripts/frontend_product_maturity_audit.mjs

ARTIFACTS_DIR="$artifacts/j02-j03" node scripts/verify/frontend_productization_fixture_browser.mjs

export_ids scripts/verify/frontend_financial_workspace_runtime_ids.py FRONTEND_FINANCIAL_WORKSPACE_TARGETS_JSON=
ARTIFACTS_DIR="$artifacts/j04-j06" node scripts/verify/frontend_financial_workspace_browser.mjs

export_ids scripts/verify/frontend_my_work_approval_runtime_ids.py FRONTEND_MY_WORK_APPROVAL_TARGETS_JSON=
ARTIFACTS_DIR="$artifacts/j07-j08" node scripts/verify/frontend_my_work_approval_browser.mjs

export_ids scripts/verify/frontend_delivery_hardening_runtime_ids.py FRONTEND_DELIVERY_HARDENING_TARGETS_JSON=
GIT_SHA="$source_sha" ARTIFACTS_DIR="$artifacts/j09-j11" node scripts/verify/frontend_delivery_hardening_browser.mjs

ARTIFACTS_DIR="$artifacts/j12-j13" node scripts/verify/frontend_core_record_form_journeys.mjs

contract_action="$(python3 -c 'import json,os; print(json.loads(os.environ["FRONTEND_FINANCIAL_WORKSPACE_TARGETS_JSON"])["contract"]["action_id"])')"
contract_menu="$(python3 -c 'import json,os; print(json.loads(os.environ["FRONTEND_FINANCIAL_WORKSPACE_TARGETS_JSON"])["contract"]["menu_id"])')"
E2E_LOGIN=fixture_role_config_admin E2E_PASSWORD="$password" \
PLATFORM_LOGIN=fixture_role_config_admin_peer PLATFORM_PASSWORD="$password" \
ORDINARY_LOGIN=fixture_role_project_a_member ORDINARY_PASSWORD="$password" \
CHANGE_SET_ACTION_ID="$contract_action" CHANGE_SET_MENU_ID="$contract_menu" \
  bash -c 'cd frontend/apps/web && node scripts/low_code_change_set_acceptance.mjs'
cp artifacts/playwright/low-code-change-set/report.json "$artifacts/low-code-change-set.json"

SOURCE_SHA="$source_sha" IMAGE_DIGEST="$actual_digest" ARTIFACTS="$artifacts" \
python3 scripts/release/verify_tenant_rc_runtime_acceptance.py
echo "[tenant.rc.runtime] PASS production-static digest=$actual_digest"
