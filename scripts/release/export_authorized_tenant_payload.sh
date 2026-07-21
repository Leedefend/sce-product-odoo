#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

image="${CANDIDATE_IMAGE:?CANDIDATE_IMAGE is required}"
expected_digest="${CANDIDATE_IMAGE_DIGEST:?CANDIDATE_IMAGE_DIGEST is required}"
backup_input="${RC_HISTORY_BACKUP:?RC_HISTORY_BACKUP is required}"
exporter_input="${RC_TENANT_PAYLOAD_EXPORTER:?RC_TENANT_PAYLOAD_EXPORTER is required}"
signing_key_input="${RC_TENANT_PAYLOAD_SIGNING_KEY:?RC_TENANT_PAYLOAD_SIGNING_KEY is required}"
public_key_input="${RC_TENANT_PAYLOAD_PUBLIC_KEY:?RC_TENANT_PAYLOAD_PUBLIC_KEY is required}"
output_input="${RC_TENANT_PAYLOAD_OUTPUT:?RC_TENANT_PAYLOAD_OUTPUT is required}"
tenant_key="${RC_TENANT_KEY:?RC_TENANT_KEY is required}"
package_manifest_input="${RC_TENANT_PACKAGE_MANIFEST:?RC_TENANT_PACKAGE_MANIFEST is required}"
payload_id="${RC_PAYLOAD_ID:?RC_PAYLOAD_ID is required}"
snapshot_id="${RC_SOURCE_SNAPSHOT_ID:?RC_SOURCE_SNAPSHOT_ID is required}"
signature_key_id="${RC_PAYLOAD_SIGNATURE_KEY_ID:?RC_PAYLOAD_SIGNATURE_KEY_ID is required}"
encryption_key_id="${RC_PAYLOAD_ENCRYPTION_KEY_ID:?RC_PAYLOAD_ENCRYPTION_KEY_ID is required}"

backup="$(realpath "$backup_input")"
exporter="$(realpath "$exporter_input")"
signing_key="$(realpath "$signing_key_input")"
public_key="$(realpath "$public_key_input")"
package_manifest="$(realpath "$package_manifest_input")"
output_parent="$(cd "$(dirname "$output_input")" && pwd)"
output="$output_parent/$(basename "$output_input")"
project="${RC_PAYLOAD_EXPORT_PROJECT:-sc-tenant-rc-payload-export}"
database="${RC_PAYLOAD_EXPORT_DB:-sc_rc_payload_export}"

[[ "$project" =~ ^sc-tenant-rc-[a-z0-9-]+$ ]] || { echo "invalid RC payload export project" >&2; exit 2; }
[[ "$database" =~ ^sc_rc_[a-z0-9_]+$ ]] || { echo "invalid RC payload export database" >&2; exit 2; }
[[ "$DB_USER" == odoo ]] || { echo "tenant payload export requires isolated DB_USER=odoo" >&2; exit 2; }
[[ -f "$exporter" && ! -L "$exporter" ]] || { echo "payload exporter must be a regular non-symlink file" >&2; exit 2; }
[[ -f "$signing_key" && ! -L "$signing_key" ]] || { echo "signing key must be a regular non-symlink file" >&2; exit 2; }
[[ -f "$public_key" && ! -L "$public_key" ]] || { echo "public key must be a regular non-symlink file" >&2; exit 2; }
[[ -f "$package_manifest" && ! -L "$package_manifest" ]] || { echo "customer package manifest must be a regular non-symlink file" >&2; exit 2; }
[[ ! -e "$output" ]] || { echo "payload output must not already exist" >&2; exit 2; }
tenant_fingerprint="$(python3 - "$package_manifest" "$tenant_key" <<'PY'
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

root = Path.cwd()
path = Path(sys.argv[1])
tenant_key = sys.argv[2]
spec = importlib.util.spec_from_file_location("customer_package_preflight", root / "scripts/release/customer_package_preflight.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = json.loads(path.read_text(encoding="utf-8"))
release = json.loads((root / "config/product_release.v1.json").read_text(encoding="utf-8"))
validated = module.load_package_manifest(path, str(manifest.get("archive_sha256") or ""), release["product_version"])
if validated["tenant_id"] != tenant_key:
    raise SystemExit("CUSTOMER_PACKAGE_TENANT_MISMATCH")
print(hashlib.sha256(tenant_key.encode("utf-8")).hexdigest()[:12])
PY
)"
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$expected_digest" ]] || {
  echo "candidate image digest mismatch" >&2
  exit 2
}

source_database="$(python3 - "$backup" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
if not manifest.get("paired") or manifest.get("production_database_write_count") != 0:
    raise SystemExit("RC_HISTORY_BACKUP_NOT_AUTHORIZED_PAIRED_COPY")
for name, expected in manifest.get("checksums", {}).items():
    path = root / name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit("RC_HISTORY_BACKUP_CHECKSUM_MISMATCH")
print(manifest["database"])
PY
)"
database_fingerprint="$(sha256sum "$backup/database.dump" | awk '{print $1}')"

compose=(docker compose -p "$project" -f docker-compose.production-candidate.yml)
export CANDIDATE_IMAGE="$image" CANDIDATE_PROJECT="$project" CANDIDATE_DB="$database"
helper="${project}-payload-reader"
cleanup() {
  docker rm -f "$helper" >/dev/null 2>&1 || true
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
"${compose[@]}" up -d --wait db redis
"${compose[@]}" exec -T db dropdb -U "$DB_USER" --if-exists "$database"
"${compose[@]}" exec -T db createdb -U "$DB_USER" "$database"
"${compose[@]}" exec -T db pg_restore -U "$DB_USER" -d "$database" --no-owner --no-privileges \
  < "$backup/database.dump"
"${compose[@]}" run --rm --no-deps --user root --entrypoint sh odoo -c \
  "rm -rf '/var/lib/odoo/filestore/$database' /tmp/rc-payload-source; mkdir -p /tmp/rc-payload-source /var/lib/odoo/filestore; tar -C /tmp/rc-payload-source -xzf -; cp -a '/tmp/rc-payload-source/$source_database' '/var/lib/odoo/filestore/$database'; rm -rf /tmp/rc-payload-source" \
  < "$backup/filestore.tar.gz"
"${compose[@]}" run -d --name "$helper" --no-deps --user root --entrypoint sleep odoo infinity >/dev/null
db_container="$("${compose[@]}" ps -q db)"

AUTHORIZED_SOURCE_DATABASES="$database" python3 "$exporter" \
  --db-container "$db_container" --odoo-container "$helper" --source-database "$database" \
  --output "$output" --signing-key "$signing_key" --signature-key-id "$signature_key_id" \
  --encryption-key-id "$encryption_key_id" --payload-id "$payload_id" \
  --source-snapshot-id "$snapshot_id" --source-database-fingerprint "$database_fingerprint"
SC_TENANT_PAYLOAD_PUBLIC_KEY="$public_key" python3 scripts/tenant_payload/cli.py validate \
  --payload "$output" --tenant-key "$tenant_key"
chmod -R go-rwx "$output"
printf '[tenant.rc.payload.export] PASS tenant_fingerprint=%s database_write_scope=isolated\n' \
  "$tenant_fingerprint"
