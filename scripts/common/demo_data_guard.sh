#!/usr/bin/env bash
set -euo pipefail

guard_demo_data_scope() {
  if [[ "${DB_NAME:-}" != "sc_demo" && "${DB_NAME:-}" != sc_demo_* ]]; then
    echo "[DENY] demo data requires a sc_demo database (got ${DB_NAME:-<empty>})" >&2
    return 30
  fi
  if [[ "${SC_ENVIRONMENT:-}" != "demo" ]]; then
    echo "[DENY] demo data requires SC_ENVIRONMENT=demo" >&2
    return 31
  fi
  if [[ "${SC_ALLOW_DEMO_DATA:-}" != "1" ]]; then
    echo "[DENY] demo data requires SC_ALLOW_DEMO_DATA=1" >&2
    return 32
  fi
}
