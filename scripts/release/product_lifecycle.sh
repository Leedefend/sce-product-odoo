#!/usr/bin/env bash
set -euo pipefail

action="${1:?product lifecycle action is required}"
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
compose=(docker compose -p "$project" -f docker-compose.production-candidate.yml)
if [[ -n "${PRODUCT_PROFILE_COMPOSE:-}" ]]; then
  compose+=( -f "$PRODUCT_PROFILE_COMPOSE" )
fi
export CANDIDATE_IMAGE="$image" CANDIDATE_DB="$database" CANDIDATE_PROJECT="$project"

run_modules() {
  local flag="$1"
  "${compose[@]}" up -d --wait db redis odoo
  "${compose[@]}" stop odoo >/dev/null
  "${compose[@]}" run --rm --no-deps --entrypoint odoo odoo \
    -c /var/lib/odoo/odoo.conf -d "$database" "$flag" "$modules" \
    --without-demo=all --workers=0 --max-cron-threads=0 --no-http --stop-after-init
}

verify_product() {
  "${compose[@]}" up -d --wait db redis
  local counts
  counts="$("${compose[@]}" exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$database" -At -F '|' -c "
SELECT
  count(*) FILTER (WHERE state IN ('to install','to upgrade','to remove')),
  count(*) FILTER (WHERE name LIKE 'sce_customer_%' AND state='installed'),
  count(*) FILTER (WHERE name IN ('smart_construction_demo','smart_construction_acceptance_fixture') AND state='installed'),
  count(*) FILTER (WHERE name = ANY(string_to_array('$modules', ',')) AND state='installed'),
  (SELECT count(*) FROM project_project)
    + (SELECT count(*) FROM construction_contract)
    + (SELECT count(*) FROM sc_settlement_order)
    + (SELECT count(*) FROM payment_request);")"
  local pending customer demo installed business expected
  IFS='|' read -r pending customer demo installed business <<<"$counts"
  expected="$(awk -F, '{print NF}' <<<"$modules")"
  [[ "$pending" == 0 && "$customer" == 0 && "$demo" == 0 && "$installed" == "$expected" && "$business" == 0 ]] || {
    echo "[product.lifecycle] verify failed pending=$pending customer=$customer demo=$demo installed=$installed/$expected business=$business" >&2
    exit 1
  }
  printf '[product.lifecycle] PASS database=%s modules=%s pending=0 customer=0 demo=0 business=0\n' "$database" "$expected"
}

case "$action" in
  install) run_modules -i ;;
  upgrade) run_modules -u ;;
  verify) verify_product ;;
  *) echo "[product.lifecycle] unsupported action: $action" >&2; exit 2 ;;
esac
