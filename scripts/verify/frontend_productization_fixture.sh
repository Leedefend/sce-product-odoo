#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export ROOT_DIR

source "$ROOT_DIR/scripts/common/frontend_acceptance_guard.sh"
guard_frontend_acceptance_scope
if [[ -z "${SC_ACCEPTANCE_FIXTURE_PASSWORD:-}" ]]; then
  echo "[DENY] frontend acceptance fixture verification requires SC_ACCEPTANCE_FIXTURE_PASSWORD" >&2
  exit 24
fi
source "$ROOT_DIR/scripts/common/env.sh"
source "$ROOT_DIR/scripts/common/guard_prod.sh"
guard_prod_forbid

export DB_NAME SC_ENVIRONMENT SC_ALLOW_DEMO_DATA SC_ACCEPTANCE_FIXTURE_PASSWORD
bash scripts/ops/odoo_shell_exec.sh < scripts/verify/frontend_productization_fixture.py
bash scripts/ops/odoo_shell_exec.sh < scripts/verify/frontend_productization_fixture_nonfixture_regression.py
