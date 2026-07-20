#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

profile="${BOUNDARY_Q11_PROFILE:?BOUNDARY_Q11_PROFILE is required}"
image="${CANDIDATE_IMAGE:?CANDIDATE_IMAGE is required}"
artifacts="${BOUNDARY_Q11_ARTIFACTS:?BOUNDARY_Q11_ARTIFACTS is required}"
db_user="${DB_USER:?DB_USER is required}"
db_password="${DB_PASSWORD:?DB_PASSWORD is required}"

case "$profile" in
  product)
    project="sc-boundary-q11-product"
    database="sc_boundary_q11_product"
    modules="smart_construction_bundle"
    customer_root=""
    ;;
  sample)
    project="sc-boundary-q11-sample"
    database="sc_boundary_q11_sample"
    modules="sce_customer_sample"
    customer_root="$root/customer_addons"
    ;;
  *)
    echo "unsupported Q11 profile: $profile" >&2
    exit 2
    ;;
esac

mkdir -p "$artifacts"
compose=(docker compose -p "$project" -f docker-compose.production-candidate.yml)
if [[ -n "${BOUNDARY_Q11_COMPOSE_OVERRIDE:-}" ]]; then
  compose+=(-f "$BOUNDARY_Q11_COMPOSE_OVERRIDE")
fi
if [[ -n "$customer_root" ]]; then
  compose+=(-f docker-compose.customer-addons.yml)
  export SC_CUSTOMER_ADDONS_ROOT="$customer_root"
fi
export CANDIDATE_IMAGE="$image" CANDIDATE_DB="$database" CANDIDATE_PROJECT="$project"

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
"${compose[@]}" up -d --wait db redis

run_odoo() {
  local mode="$1" log="$2"
  set +e
  "${compose[@]}" run --rm --no-deps --entrypoint odoo odoo \
    --db_host=db --db_port=5432 --db_user="$db_user" --db_password="$db_password" \
    --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/product-addons,/mnt/customer-addons,/mnt/addons_external/oca_server_ux \
    --data-dir=/var/lib/odoo -d "$database" --no-http --workers=0 --max-cron-threads=0 \
    "$mode" "$modules" --without-demo=all --stop-after-init 2>&1 | tee "$log"
  status="${PIPESTATUS[0]}"
  set -e
  [[ "$status" == 0 ]] || return "$status"
}

run_odoo -i "$artifacts/install.log"
run_odoo -u "$artifacts/upgrade-1.log"
run_odoo -u "$artifacts/upgrade-2.log"

sql="${artifacts}/runtime.sql"
cat > "$sql" <<'SQL'
\pset tuples_only on
\pset format unaligned
SELECT 'pending_modules=' || count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');
SELECT 'legacy_models=' || count(*) FROM ir_model WHERE model LIKE 'sc.legacy.%' OR model IN ('sc.history.todo','sc.project.member.staging');
SELECT 'legacy_fields=' || count(*)
  FROM ir_model_fields
 WHERE model IN ('res.partner','project.project','construction.contract','sc.business.entity')
   AND (name ~ '^legacy_' OR name IN ('mapping_state','map_ids'));
SELECT 'customer_modules_installed=' || count(*) FROM ir_module_module WHERE name LIKE 'sce_customer_%' AND state='installed';
SELECT 'demo_modules_installed=' || count(*) FROM ir_module_module WHERE name IN ('smart_construction_demo','smart_construction_acceptance_fixture') AND state='installed';
SELECT 'business_rows=' || (
  (SELECT count(*) FROM project_project) +
  (SELECT count(*) FROM construction_contract) +
  (SELECT count(*) FROM sc_settlement_order) +
  (SELECT count(*) FROM payment_request)
);
SQL
"${compose[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "$db_user" -d "$database" -f - < "$sql" > "$artifacts/runtime-counts.txt"

PROFILE="$profile" DATABASE="$database" MODULES="$modules" ARTIFACTS="$artifacts" python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ARTIFACTS"])
counts = {}
for line in (root / "runtime-counts.txt").read_text().splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        counts[key.strip()] = int(value.strip())
profile = os.environ["PROFILE"]
errors = []
if counts.get("pending_modules") != 0:
    errors.append("pending_modules")
if counts.get("demo_modules_installed") != 0:
    errors.append("demo_or_fixture_installed")
if profile == "product":
    if counts.get("legacy_models") != 0:
        errors.append("customer_legacy_models_visible")
    if counts.get("legacy_fields") != 0:
        errors.append("customer_legacy_fields_visible")
    if counts.get("customer_modules_installed") != 0:
        errors.append("customer_module_installed")
    if counts.get("business_rows") != 0:
        errors.append("unexpected_business_rows")
elif profile == "sample":
    if counts.get("customer_modules_installed") != 1:
        errors.append("sample_customer_module_not_installed")
payload = {
    "schema_version": 1,
    "profile": profile,
    "database": os.environ["DATABASE"],
    "modules": os.environ["MODULES"].split(","),
    "install": "PASS",
    "upgrade_once": "PASS",
    "upgrade_twice": "PASS",
    "counts": counts,
    "errors": errors,
    "pass": not errors,
    "production_writes": 0,
}
(root / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
if errors:
    raise SystemExit("Q11 profile failed: " + ",".join(errors))
print(f"[tenant_boundary_q11] PASS profile={profile} counts={counts}")
PY
