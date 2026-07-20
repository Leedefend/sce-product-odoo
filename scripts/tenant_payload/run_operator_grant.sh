#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_lib/common.sh"

[[ -n "${DB_NAME:-}" ]] || { echo "DB_NAME is required" >&2; exit 2; }
[[ -n "${TENANT_PAYLOAD_OPERATOR_LOGIN:-}" ]] || { echo "TENANT_PAYLOAD_OPERATOR_LOGIN is required" >&2; exit 2; }
[[ -n "${TENANT_PAYLOAD_DB_ALLOWLIST:-}" ]] || { echo "TENANT_PAYLOAD_DB_ALLOWLIST is required" >&2; exit 2; }
[[ -n "${APPROVED_BY:-}" ]] || { echo "APPROVED_BY is required" >&2; exit 2; }
if [[ -n "${SC_CUSTOMER_ADDONS_ROOT:-}" ]]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.customer-addons.yml"
fi

compose run --rm --no-deps -T \
  --user odoo \
  -e "SC_TENANT_PAYLOAD_OPERATOR_LOGIN=$TENANT_PAYLOAD_OPERATOR_LOGIN" \
  -e "SC_TENANT_PAYLOAD_DB_ALLOWLIST=$TENANT_PAYLOAD_DB_ALLOWLIST" \
  -e "SC_TENANT_PAYLOAD_APPROVED_BY=$APPROVED_BY" \
  -e "SC_TENANT_PAYLOAD_CREATE_OPERATOR=${CREATE_OPERATOR:-0}" \
  -e "SC_TENANT_PAYLOAD_TEST_MODE=${SC_TENANT_PAYLOAD_TEST_MODE:-0}" \
  --entrypoint odoo \
  odoo shell -d "$DB_NAME" -c /var/lib/odoo/odoo.conf \
  < scripts/tenant_payload/provision_operator.py
