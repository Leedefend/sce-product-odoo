#!/usr/bin/env bash
set -euo pipefail

action="${1:?profile action is required}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

image="${CANDIDATE_IMAGE:?CANDIDATE_IMAGE is required}"
expected_digest="${CANDIDATE_IMAGE_DIGEST:?CANDIDATE_IMAGE_DIGEST is required}"
artifacts="${CANDIDATE_ARTIFACTS:?CANDIDATE_ARTIFACTS is required}"
mkdir -p "$artifacts/profiles" "$artifacts/empty-mounts/customer" \
  "$artifacts/empty-mounts/payload" "$artifacts/empty-mounts/attachments"
artifacts="$(realpath "$artifacts")"
empty="$artifacts/empty-mounts"
actual_digest="$(docker image inspect "$image" --format '{{.Id}}')"
[[ "$actual_digest" == "$expected_digest" ]] || {
  echo "[tenant.rc.profile] image digest mismatch" >&2
  exit 2
}
product_modules="$(python3 scripts/ops/tenant_module_set.py product)"

case "$action" in
  product)
    profile=RC-C01
    project="${RC_PROJECT:-sc-tenant-rc-c01}"
    database="${RC_DATABASE:-sc_rc_product}"
    modules="$product_modules"
    customer_root="$empty/customer"
    payload_root="$empty/payload"
    tenant_id=""
    ;;
  sample)
    profile=RC-C04
    project="${RC_PROJECT:-sc-tenant-rc-c04}"
    database="${RC_DATABASE:-sc_rc_sample}"
    customer_module="${RC_SYNTHETIC_CUSTOMER_MODULE:?RC_SYNTHETIC_CUSTOMER_MODULE is required}"
    tenant_id="${RC_SYNTHETIC_TENANT_KEY:?RC_SYNTHETIC_TENANT_KEY is required}"
    module_version="${RC_SYNTHETIC_MODULE_VERSION:?RC_SYNTHETIC_MODULE_VERSION is required}"
    customer_root="$(realpath "${RC_CUSTOMER_ADDONS_ROOT:?RC_CUSTOMER_ADDONS_ROOT is required}")"
    modules="$product_modules,$customer_module"
    payload_root="$artifacts/synthetic-payload"
    rm -rf "$payload_root"
    payload_hmac="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    SC_TENANT_PAYLOAD_TEST_MODE=1 SC_TENANT_PAYLOAD_HMAC_KEY="$payload_hmac" \
      python3 scripts/tenant_payload/build_synthetic_payload.py --output "$payload_root" \
        --tenant-key "$tenant_id" --module-version "$module_version" \
        > "$artifacts/profiles/RC-C04-payload-build.json"
    SC_TENANT_PAYLOAD_TEST_MODE=1 SC_TENANT_PAYLOAD_HMAC_KEY="$payload_hmac" \
      python3 scripts/tenant_payload/cli.py validate --payload "$payload_root" \
        --tenant-key "$tenant_id" > "$artifacts/profiles/RC-C04-payload-validate.json"
    ;;
  customer)
    profile=RC-C03
    project="${RC_PROJECT:-sc-tenant-rc-c03}"
    database="${RC_DATABASE:-sc_rc_customer}"
    customer_module="${SC_CUSTOMER_MODULE:?SC_CUSTOMER_MODULE is required}"
    tenant_id="${SC_TENANT_ID:?SC_TENANT_ID is required}"
    legacy_customer_module="${RC_LEGACY_CUSTOMER_MODULE:?RC_LEGACY_CUSTOMER_MODULE is required}"
    history_backup="$(realpath "${RC_HISTORY_BACKUP:?RC_HISTORY_BACKUP is required}")"
    identity_migration="$(realpath "${RC_CUSTOMER_IDENTITY_MIGRATION:?RC_CUSTOMER_IDENTITY_MIGRATION is required}")"
    payload_manifest="$(realpath "${SC_PAYLOAD_MANIFEST:?SC_PAYLOAD_MANIFEST is required}")"
    payload_root="$(dirname "$payload_manifest")"
    prepared="$artifacts/prepared-customer"
    rm -rf "$prepared"
    python3 scripts/release/customer_package_preflight.py --prepare-dir "$prepared" \
      --report "$artifacts/profiles/RC-C03-package-admission.json" \
      > "$artifacts/profiles/RC-C03-package-admission.stdout.json"
    customer_root="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["prepared_addons_root"])' "$artifacts/profiles/RC-C03-package-admission.json")"
    modules="$product_modules,$customer_module,$legacy_customer_module"
    ;;
  *) echo "unknown profile action: $action" >&2; exit 2 ;;
esac

[[ "$project" =~ ^sc-tenant-rc-[a-z0-9-]+$ ]] || { echo "invalid RC project" >&2; exit 2; }
[[ "$database" =~ ^sc_rc_[a-z0-9_]+$ ]] || { echo "invalid RC database" >&2; exit 2; }
compose=(docker compose -p "$project" -f docker-compose.production-candidate.yml -f docker-compose.tenant-rc-profile.yml)
export CANDIDATE_IMAGE="$image" CANDIDATE_PROJECT="$project" CANDIDATE_DB="$database"
export RC_CUSTOMER_ADDONS_MOUNT="$customer_root" RC_PAYLOAD_ROOT_MOUNT="$payload_root"
export RC_ATTACHMENT_PROVIDER_ROOT="$(realpath "${RC_CURATED_ASSET_ROOT:-$empty/attachments}")"
export RC_PAYLOAD_MANIFEST_CONTAINER="/mnt/tenant-payload/manifest.json"
export SC_TENANT_ID="$tenant_id" SC_CUSTOMER_MODULE="${customer_module:-}"

cleanup() { "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
"${compose[@]}" up -d --wait db redis

if [[ "$profile" == RC-C03 ]]; then
  python3 - "$history_backup" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
if not manifest.get("paired"):
    raise SystemExit("RC_HISTORY_BACKUP_NOT_PAIRED")
for name, expected in manifest["checksums"].items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
        raise SystemExit("RC_HISTORY_BACKUP_CHECKSUM_MISMATCH")
PY
  source_database="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["database"])' "$history_backup/manifest.json")"
  "${compose[@]}" exec -T db dropdb -U "$DB_USER" --if-exists "$database"
  "${compose[@]}" exec -T db createdb -U "$DB_USER" "$database"
  "${compose[@]}" exec -T db pg_restore -U "$DB_USER" -d "$database" --no-owner --no-privileges \
    < "$history_backup/database.dump"
  "${compose[@]}" run --rm --no-deps --user root --entrypoint sh odoo -c \
    "rm -rf '/var/lib/odoo/filestore/$database' /tmp/rc-filestore; mkdir -p /tmp/rc-filestore /var/lib/odoo/filestore; tar -C /tmp/rc-filestore -xzf -; cp -a '/tmp/rc-filestore/$source_database' '/var/lib/odoo/filestore/$database'; rm -rf /tmp/rc-filestore" \
    < "$history_backup/filestore.tar.gz"
fi

# Render the production configuration without starting the registry.  This is
# essential for a historical copy whose old customer module identity is
# intentionally migrated by the next audited step.
"${compose[@]}" run --rm --no-deps --entrypoint python3 odoo \
  /usr/local/bin/render_odoo_conf.py /etc/odoo/odoo.conf.template /var/lib/odoo/odoo.conf

if [[ "$profile" == RC-C03 ]]; then
  "${compose[@]}" run --rm --no-deps -T --user odoo -e SC_CONFIRM_CUSTOMER_MODULE_RENAME=1 \
    --entrypoint odoo odoo shell -d "$database" -c /var/lib/odoo/odoo.conf --log-level=error \
    < "$identity_migration" > "$artifacts/profiles/RC-C03-module-identity.json"
fi

run_modules() {
  local -a projection_handoff=()
  if [[ "$profile" == RC-C03 ]]; then
    projection_handoff=(-e SC_ALLOW_EXTERNAL_PROJECTION_HANDOFF=1)
  fi
  "${compose[@]}" run --rm --no-deps "${projection_handoff[@]}" --entrypoint odoo odoo \
    -c /var/lib/odoo/odoo.conf -d "$database" "$@" --without-demo=all \
    --workers=0 --max-cron-threads=0 --no-http --stop-after-init
}
run_modules -i "$modules"
run_modules -i "$modules" -u "$modules"
run_modules -i "$modules" -u "$modules"

if [[ "$profile" == RC-C04 ]]; then
  operator="svc_rc_sample_payload"
  "${compose[@]}" run --rm --no-deps -T --user odoo \
    -e "SC_TENANT_PAYLOAD_OPERATOR_LOGIN=$operator" -e "SC_TENANT_PAYLOAD_DB_ALLOWLIST=$database" \
    -e SC_TENANT_PAYLOAD_APPROVED_BY=tenant-rc-synthetic -e SC_TENANT_PAYLOAD_CREATE_OPERATOR=1 \
    -e SC_TENANT_PAYLOAD_TEST_MODE=1 --entrypoint odoo odoo shell -d "$database" \
    -c /var/lib/odoo/odoo.conf --log-level=error < scripts/tenant_payload/provision_operator.py \
    > "$artifacts/profiles/RC-C04-operator.json"
  for payload_action in plan import verify import verify; do
    "${compose[@]}" run --rm --no-deps -T --user odoo \
      -e "SC_TENANT_PAYLOAD_ACTION=$payload_action" -e "SC_TENANT_PAYLOAD_TENANT_KEY=$tenant_id" \
      -e "SC_TENANT_PAYLOAD_OPERATOR_LOGIN=$operator" -e "SC_TENANT_PAYLOAD_DB_ALLOWLIST=$database" \
      -e "SC_TENANT_PAYLOAD_HMAC_KEY=$payload_hmac" -e SC_TENANT_PAYLOAD_TEST_MODE=1 \
      --entrypoint odoo odoo shell -d "$database" -c /var/lib/odoo/odoo.conf --log-level=error \
      < scripts/tenant_payload/odoo_action.py >> "$artifacts/profiles/RC-C04-payload-${payload_action}.jsonl"
  done
  python3 - "$artifacts/profiles/RC-C04-payload-import.jsonl" \
    "$artifacts/profiles/RC-C04-payload-verify.jsonl" <<'PY'
import json
import sys
from pathlib import Path


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


imports = load_jsonl(sys.argv[1])
verifications = load_jsonl(sys.argv[2])
if len(imports) != 2 or len(verifications) != 2:
    raise SystemExit("RC_C04_IDEMPOTENCY_RESULT_COUNT_INVALID")
if imports[0].get("idempotent_noop") is not False:
    raise SystemExit("RC_C04_FIRST_IMPORT_MUST_APPLY")
if imports[1].get("idempotent_noop") is not True:
    raise SystemExit("RC_C04_SECOND_IMPORT_MUST_BE_NOOP")
if any(result.get("status") != "PASS" for result in imports + verifications):
    raise SystemExit("RC_C04_PAYLOAD_RESULT_FAILED")
if len({result.get("payload_checksum") for result in imports + verifications}) != 1:
    raise SystemExit("RC_C04_PAYLOAD_CHECKSUM_DRIFT")
PY
fi

metrics="$("${compose[@]}" exec -T db psql -U "$DB_USER" -d "$database" -At -F '|' -c "
SELECT
  count(*) FILTER (WHERE state IN ('to install','to upgrade','to remove')),
  count(*) FILTER (WHERE name IN ('smart_construction_demo','smart_construction_acceptance_fixture') AND state='installed'),
  count(*) FILTER (WHERE name LIKE 'sce_customer_%' AND state='installed'),
  (SELECT count(*) FROM project_project) + (SELECT count(*) FROM construction_contract)
    + (SELECT count(*) FROM sc_settlement_order) + (SELECT count(*) FROM payment_request)
FROM ir_module_module;")"
IFS='|' read -r pending demo_fixture customer_count business_count <<< "$metrics"
case "$profile" in
  RC-C01) [[ "$pending" == 0 && "$demo_fixture" == 0 && "$customer_count" == 0 && "$business_count" == 0 ]] ;;
  RC-C04) [[ "$pending" == 0 && "$demo_fixture" == 0 && "$customer_count" == 1 && "$business_count" -gt 0 ]] ;;
  RC-C03) [[ "$pending" == 0 && "$demo_fixture" == 0 && "$customer_count" -ge 2 && "$business_count" -gt 0 ]] ;;
esac

PROFILE="$profile" DATABASE="$database" MODULES="$modules" DIGEST="$actual_digest" \
PENDING="$pending" DEMO_FIXTURE="$demo_fixture" CUSTOMER_COUNT="$customer_count" BUSINESS_COUNT="$business_count" \
python3 - "$artifacts/profiles/${profile}.json" <<'PY'
import json, os, sys
from pathlib import Path
payload = {
    "schema_version": 1, "profile": os.environ["PROFILE"], "database": os.environ["DATABASE"],
    "product_image_digest": os.environ["DIGEST"], "installed_entry_modules": os.environ["MODULES"].split(","),
    "upgrade_runs": 2, "pending_modules": int(os.environ["PENDING"]),
    "demo_or_fixture_installed": int(os.environ["DEMO_FIXTURE"]),
    "customer_modules_installed": int(os.environ["CUSTOMER_COUNT"]),
    "business_record_count": int(os.environ["BUSINESS_COUNT"]), "pass": True,
}
Path(sys.argv[1]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
echo "[tenant.rc.profile] $profile PASS digest=$actual_digest pending=0"
