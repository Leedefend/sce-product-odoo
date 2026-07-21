#!/usr/bin/env bash
set -euo pipefail

database="${ODOO_DB:?ODOO_DB is required}"
[[ "$database" =~ ^[a-zA-Z0-9_]+$ ]] || {
  echo "[nginx.config] invalid ODOO_DB" >&2
  exit 2
}

envsubst '$ODOO_DB' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
printf 'window.__SC_RUNTIME_CONFIG__ = Object.freeze({"odooDb":"%s","odooDbLocked":true});\n' \
  "$database" > /usr/share/nginx/html/runtime-config.js
exec /usr/sbin/nginx -g 'daemon off;'
