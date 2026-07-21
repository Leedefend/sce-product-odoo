#!/usr/bin/env bash
set -euo pipefail

action="${1:?product lifecycle action is required}"
mode="${PRODUCT_LIFECYCLE_MODE:-product-only}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

database="${DB_NAME:?DB_NAME is required}"
image="${CANDIDATE_IMAGE:?CANDIDATE_IMAGE is required}"
project="${PRODUCT_PROJECT:-sc-tenant-rc-product}"
case "$database" in
  sc_rc_[a-z0-9_]*) ;;
  *) echo "[product.lifecycle] isolated DB_NAME must start with sc_rc_" >&2; exit 2 ;;
esac
[[ "$project" =~ ^sc-tenant-rc-[a-z0-9-]+$ ]] || {
  echo "[product.lifecycle] invalid isolated compose project" >&2
  exit 2
}
modules="$(python3 scripts/ops/tenant_module_set.py product)"
customer_modules=""
compose=(docker compose -p "$project" -f docker-compose.production-candidate.yml)
case "$mode" in
  product-only) ;;
  product-with-external-customer-package)
    package_manifest="${SC_CUSTOMER_PACKAGE_MANIFEST:?SC_CUSTOMER_PACKAGE_MANIFEST is required}"
    customer_archive_root="${SC_CUSTOMER_ADDONS_ROOT:?SC_CUSTOMER_ADDONS_ROOT is required}"
    customer_archive_sha="${SC_CUSTOMER_ARCHIVE_SHA256:?SC_CUSTOMER_ARCHIVE_SHA256 is required}"
    lifecycle_artifacts="${CANDIDATE_ARTIFACTS:-artifacts/release/product-lifecycle}"
    prepared="$lifecycle_artifacts/prepared-customer-addons"
    report="$lifecycle_artifacts/customer-package-admission.json"
    rm -rf "$prepared"
    SC_CUSTOMER_PACKAGE_MANIFEST="$package_manifest" \
      SC_CUSTOMER_ADDONS_ROOT="$customer_archive_root" \
      SC_CUSTOMER_ARCHIVE_SHA256="$customer_archive_sha" \
      python3 scripts/release/customer_package_preflight.py \
        --prepare-dir "$prepared" --report "$report" >/dev/null
    customer_modules="$(python3 - "$report" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
modules = payload.get("modules")
if not isinstance(modules, list) or not modules:
    raise SystemExit("CUSTOMER_PACKAGE_MODULES_MISSING")
print(",".join(modules))
PY
)"
    SC_CUSTOMER_ADDONS_ROOT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["prepared_addons_root"])' "$report")"
    export SC_CUSTOMER_ADDONS_ROOT
    modules="$modules,$customer_modules"
    compose+=( -f docker-compose.customer-addons.yml )
    ;;
  *) echo "[product.lifecycle] unsupported mode: $mode" >&2; exit 2 ;;
esac
if [[ -n "${PRODUCT_PROFILE_COMPOSE:-}" ]]; then
  compose+=( -f "$PRODUCT_PROFILE_COMPOSE" )
fi
export CANDIDATE_IMAGE="$image" CANDIDATE_DB="$database" CANDIDATE_PROJECT="$project"
mkdir -p artifacts/release/rc-empty/customer artifacts/release/rc-empty/payload \
  artifacts/release/rc-empty/attachments

run_modules() {
  local flags=("$@")
  "${compose[@]}" up -d --wait db redis odoo
  "${compose[@]}" stop odoo >/dev/null
  "${compose[@]}" run --rm --no-deps --entrypoint odoo odoo \
    -c /var/lib/odoo/odoo.conf -d "$database" "${flags[@]}" \
    --without-demo=all --workers=0 --max-cron-threads=0 --no-http --stop-after-init
}

verify_product() {
  "${compose[@]}" up -d --wait db redis
  local counts
  counts="$("${compose[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$database" -At -F '|' -c "
SELECT
  (SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')),
  (SELECT count(*) FROM ir_module_module
    WHERE name = ANY(string_to_array(NULLIF('$customer_modules',''), ',')) AND state='installed'),
  (SELECT count(*) FROM ir_module_module WHERE name IN ('smart_construction_demo','smart_construction_acceptance_fixture') AND state='installed'),
  (SELECT count(*) FROM ir_module_module WHERE name = ANY(string_to_array('$modules', ',')) AND state='installed'),
  (SELECT count(*) FROM project_project)
    + (SELECT count(*) FROM construction_contract)
    + (SELECT count(*) FROM sc_settlement_order)
    + (SELECT count(*) FROM payment_request);")"
  local pending customer demo installed business expected
  IFS='|' read -r pending customer demo installed business <<<"$counts"
  expected="$(awk -F, '{print NF}' <<<"$modules")"
  local expected_customer=0
  if [[ -n "$customer_modules" ]]; then
    expected_customer="$(awk -F, '{print NF}' <<<"$customer_modules")"
  fi
  [[ "$pending" == 0 && "$customer" == "$expected_customer" && "$demo" == 0 && "$installed" == "$expected" && "$business" == 0 ]] || {
    echo "[product.lifecycle] verify failed pending=$pending customer=$customer demo=$demo installed=$installed/$expected business=$business" >&2
    exit 1
  }
  printf '[product.lifecycle] PASS mode=%s modules=%s pending=0 external_modules=%s demo=0 business=0\n' \
    "$mode" "$expected" "$expected_customer"
}

case "$action" in
  install) run_modules -i "$modules" ;;
  upgrade) run_modules -i "$modules" -u "$modules" ;;
  verify) verify_product ;;
  *) echo "[product.lifecycle] unsupported action: $action" >&2; exit 2 ;;
esac
