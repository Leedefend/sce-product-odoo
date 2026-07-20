#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_lib/common.sh"

if [[ -n "${SC_CUSTOMER_ADDONS_ROOT:-}" ]]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.customer-addons.yml"
fi

action="${SC_TENANT_PAYLOAD_ACTION:-}"
payload="${TENANT_PAYLOAD:-}"
tenant_key="${TENANT_KEY:-}"
operator_login="${TENANT_PAYLOAD_OPERATOR_LOGIN:-}"
database_allowlist="${TENANT_PAYLOAD_DB_ALLOWLIST:-}"

[[ "$action" =~ ^(plan|import|verify|reconcile)$ ]] || { echo "TPV1_ACTION_INVALID" >&2; exit 2; }
[[ -n "$payload" && -d "$payload" && ! -L "$payload" ]] || { echo "TPV1_ROOT_INVALID" >&2; exit 2; }
[[ -n "${DB_NAME:-}" ]] || { echo "DB_NAME is required" >&2; exit 2; }
[[ -n "$tenant_key" ]] || { echo "TENANT_KEY is required" >&2; exit 2; }
[[ -n "$operator_login" ]] || { echo "TENANT_PAYLOAD_OPERATOR_LOGIN is required" >&2; exit 2; }
[[ -n "$database_allowlist" ]] || { echo "TENANT_PAYLOAD_DB_ALLOWLIST is required" >&2; exit 2; }

payload_root="$(realpath "$payload")"
payload_gid="$(stat -c %g "$payload_root")"
[[ "$payload_gid" =~ ^[0-9]+$ ]] || { echo "TPV1_ROOT_GROUP_INVALID" >&2; exit 2; }
export SC_TENANT_PAYLOAD_HOST_GID="$payload_gid"
COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.tenant-payload.yml"
repo_root="$(git rev-parse --show-toplevel)"
case "$payload_root/" in
  "$repo_root/"*)
    if [[ "${SC_TENANT_PAYLOAD_TEST_MODE:-}" != "1" ]]; then
      echo "TPV1_REAL_PAYLOAD_INSIDE_REPOSITORY_FORBIDDEN" >&2
      exit 2
    fi
    git check-ignore -q "$payload_root" || {
      echo "TPV1_SYNTHETIC_PAYLOAD_MUST_BE_IGNORED" >&2
      exit 2
    }
    ;;
esac

compose_args=(run --rm --no-deps -T)
public_key="${SC_TENANT_PAYLOAD_PUBLIC_KEY:-}"
if [[ -n "$public_key" ]]; then
  [[ -f "$public_key" && ! -L "$public_key" ]] || { echo "TPV1_PUBLIC_KEY_INVALID" >&2; exit 2; }
  public_key="$(realpath "$public_key")"
  compose_args+=(--volume "$public_key:/mnt/tenant-payload-public-key:ro")
fi

compose "${compose_args[@]}" \
  --user odoo \
  --volume "$payload_root:/mnt/tenant-payload:ro" \
  -e "SC_TENANT_PAYLOAD_ACTION=$action" \
  -e "SC_TENANT_PAYLOAD_TENANT_KEY=$tenant_key" \
  -e "SC_TENANT_PAYLOAD_OPERATOR_LOGIN=$operator_login" \
  -e "SC_TENANT_PAYLOAD_DB_ALLOWLIST=$database_allowlist" \
  -e "SC_TENANT_PAYLOAD_APPROVED_CHECKSUM=${APPROVE_PAYLOAD_CHECKSUM:-}" \
  -e "SC_TENANT_PAYLOAD_CHUNK_SIZE=${TENANT_PAYLOAD_CHUNK_SIZE:-100}" \
  -e "SC_TENANT_PAYLOAD_INTERRUPT_AFTER=${TENANT_PAYLOAD_INTERRUPT_AFTER:-}" \
  -e "SC_TENANT_PAYLOAD_RESUME_FAILED=${RESUME_FAILED:-0}" \
  -e "SC_TENANT_PAYLOAD_CONFIRM_FILESTORE_RECONCILE=${CONFIRM_TENANT_PAYLOAD_FILESTORE_RECONCILE:-0}" \
  -e "SC_TENANT_PAYLOAD_PUBLIC_KEY=$([[ -n "$public_key" ]] && printf /mnt/tenant-payload-public-key)" \
  -e "SC_TENANT_PAYLOAD_HMAC_KEY=${SC_TENANT_PAYLOAD_HMAC_KEY:-}" \
  -e "SC_TENANT_PAYLOAD_TEST_MODE=${SC_TENANT_PAYLOAD_TEST_MODE:-}" \
  --entrypoint odoo \
  odoo shell -d "$DB_NAME" -c /var/lib/odoo/odoo.conf --log-level=error \
  < scripts/tenant_payload/odoo_action.py
