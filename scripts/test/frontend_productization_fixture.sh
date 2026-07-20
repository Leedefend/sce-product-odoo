#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export ROOT_DIR

source "$ROOT_DIR/scripts/common/frontend_acceptance_guard.sh"
guard_frontend_acceptance_scope
acquire_frontend_acceptance_lock lifecycle

if [[ -z "${SC_ACCEPTANCE_FIXTURE_PASSWORD:-}" ]]; then
  echo "[DENY] frontend acceptance fixture requires SC_ACCEPTANCE_FIXTURE_PASSWORD" >&2
  exit 24
fi

source "$ROOT_DIR/scripts/common/env.sh"
source "$ROOT_DIR/scripts/common/guard_prod.sh"
guard_prod_forbid

export DB_NAME SC_ENVIRONMENT SC_ALLOW_DEMO_DATA SC_ACCEPTANCE_FIXTURE_PASSWORD

DB_NAME="$DB_NAME" bash scripts/ops/odoo_shell_exec.sh <<'PY'
import json
from odoo.addons.smart_construction_acceptance_fixture.tools.frontend_productization_fixture import ensure_fixture

summary = ensure_fixture(env)
env.cr.commit()
print("[acceptance.frontend.fixture] PASS")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
