#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_lib/common.sh"

action="${1:-}"
database="${DB_NAME:-}"
root="${TENANT_PAYLOAD_RECOVERY_ROOT:-}"
allowlist=",${TENANT_PAYLOAD_DB_ALLOWLIST:-},"
[[ "$action" =~ ^(backup|restore)$ ]] || { echo "TPV1_RECOVERY_ACTION_INVALID" >&2; exit 2; }
[[ -n "$database" && "$allowlist" == *",$database,"* ]] || { echo "TPV1_RECOVERY_DATABASE_NOT_ALLOWLISTED" >&2; exit 2; }
[[ -n "$root" && ! -L "$root" ]] || { echo "TPV1_RECOVERY_ROOT_INVALID" >&2; exit 2; }
root="$(realpath -m "$root")"
repo_root="$(git rev-parse --show-toplevel)"
case "$root/" in "$repo_root/"*) echo "TPV1_RECOVERY_INSIDE_REPOSITORY_FORBIDDEN" >&2; exit 2;; esac

db_dump="$root/database.dump"
filestore_tar="$root/filestore.tar"
manifest="$root/manifest.json"

fingerprint() {
  compose exec -T db psql -X -U "$DB_USER" -d "$database" -AtF '|' <<'SQL' | sha256sum | cut -d' ' -f1
SELECT table_name, row_count FROM (
  SELECT 'res_company' table_name,count(*) row_count FROM res_company
  UNION ALL SELECT 'res_users',count(*) FROM res_users
  UNION ALL SELECT 'res_partner',count(*) FROM res_partner
  UNION ALL SELECT 'project_project',count(*) FROM project_project
  UNION ALL SELECT 'construction_contract',count(*) FROM construction_contract
  UNION ALL SELECT 'sc_settlement_order',count(*) FROM sc_settlement_order
  UNION ALL SELECT 'payment_request',count(*) FROM payment_request
  UNION ALL SELECT 'sc_payment_execution',count(*) FROM sc_payment_execution
  UNION ALL SELECT 'payment_ledger',count(*) FROM payment_ledger
  UNION ALL SELECT 'ir_attachment',count(*) FROM ir_attachment
  UNION ALL SELECT 'tenant_payload_identity',count(*) FROM sc_tenant_payload_external_identity
  UNION ALL SELECT 'tenant_payload_batch',count(*) FROM sc_tenant_payload_import_batch
) counts ORDER BY table_name;
SQL
}

if [[ "$action" == "backup" ]]; then
  [[ ! -e "$root" ]] || { echo "TPV1_RECOVERY_BACKUP_EXISTS" >&2; exit 2; }
  install -d -m 700 "$root"
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  before="$(fingerprint)"
  compose exec -T db pg_dump -U "$DB_USER" -d "$database" -Fc > "$db_dump"
  compose exec -T odoo sh -c "mkdir -p '/var/lib/odoo/filestore/$database'; tar -C /var/lib/odoo/filestore -cf - '$database'" > "$filestore_tar"
  chmod 600 "$db_dump" "$filestore_tar"
  db_sha="$(sha256sum "$db_dump" | cut -d' ' -f1)"
  fs_sha="$(sha256sum "$filestore_tar" | cut -d' ' -f1)"
  DB_NAME_VALUE="$database" STARTED="$started" DB_SHA="$db_sha" FS_SHA="$fs_sha" FP="$before" ROOT="$root" python3 - <<'PY'
import json, os
from pathlib import Path
root=Path(os.environ["ROOT"])
payload={"schema_version":"tenant_payload.paired_recovery.v1","database":os.environ["DB_NAME_VALUE"],"created_at_utc":os.environ["STARTED"],"database_fingerprint":os.environ["FP"],"checksums":{"database.dump":os.environ["DB_SHA"],"filestore.tar":os.environ["FS_SHA"]}}
(root/"manifest.json").write_text(json.dumps(payload,sort_keys=True)+"\n",encoding="utf-8")
(root/"manifest.json").chmod(0o600)
PY
  echo "TPV1_RECOVERY_BACKUP_PASS fingerprint_prefix=${before:0:16}"
  exit 0
fi

[[ "${CONFIRM_TENANT_PAYLOAD_PAIRED_RESTORE:-}" == "1" ]] || { echo "TPV1_RECOVERY_RESTORE_CONFIRMATION_REQUIRED" >&2; exit 2; }
[[ -f "$db_dump" && -f "$filestore_tar" && -f "$manifest" ]] || { echo "TPV1_RECOVERY_SET_INCOMPLETE" >&2; exit 2; }
python3 - "$root" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); manifest=json.loads((root/"manifest.json").read_text())
for name,want in manifest["checksums"].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=want: raise SystemExit("TPV1_RECOVERY_CHECKSUM_MISMATCH")
PY
started_seconds="$(date +%s)"
compose exec -T db psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$database' AND pid <> pg_backend_pid()" >/dev/null
compose exec -T db dropdb -U "$DB_USER" "$database"
compose exec -T db createdb -U "$DB_USER" "$database"
compose exec -T db pg_restore -U "$DB_USER" -d "$database" --no-owner --no-privileges < "$db_dump"
quarantine="/var/lib/odoo/filestore/${database}.failed-import.$(date +%s)"
compose exec -T odoo sh -c "set -e; test ! -e '$quarantine'; if test -e '/var/lib/odoo/filestore/$database'; then mv '/var/lib/odoo/filestore/$database' '$quarantine'; fi; tar -C /var/lib/odoo/filestore -xf -" < "$filestore_tar"
after="$(fingerprint)"
expected="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["database_fingerprint"])' "$manifest")"
[[ "$after" == "$expected" ]] || { echo "TPV1_RECOVERY_FINGERPRINT_MISMATCH" >&2; exit 1; }
duration="$(( $(date +%s) - started_seconds ))"
echo "TPV1_RECOVERY_RESTORE_PASS fingerprint_prefix=${after:0:16} rto_seconds=$duration"
