#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export ROOT_DIR

source "$ROOT_DIR/scripts/common/frontend_acceptance_guard.sh"
guard_frontend_acceptance_scope
acquire_frontend_acceptance_lock lifecycle

source "$ROOT_DIR/scripts/common/env.sh"
source "$ROOT_DIR/scripts/common/guard_prod.sh"
guard_prod_forbid

export DB_NAME SC_ENVIRONMENT SC_ALLOW_DEMO_DATA

make --no-print-directory db.create DB="$DB_NAME"
make --no-print-directory mod.install \
  MODULE=smart_construction_bootstrap,smart_construction_bundle,smart_construction_seed,smart_construction_acceptance_fixture \
  DB_NAME="$DB_NAME"
DB_NAME="$DB_NAME" bash scripts/ops/odoo_shell_exec.sh <<'PY'
param = env['ir.config_parameter'].sudo().get_param('smart_core.release_operator.product_base_keys', '')
states = {
    row.name: row.state
    for row in env['ir.module.module'].sudo().search([
        ('name', 'in', [
            'smart_construction_bundle',
            'smart_construction_seed',
            'smart_construction_acceptance_fixture',
            'smart_construction_demo',
        ])
    ])
}
if states.get('smart_construction_bundle') != 'installed' or 'construction' not in [v.strip() for v in param.split(',') if v.strip()]:
    raise RuntimeError('acceptance product baseline is not initialized')
if states.get('smart_construction_seed') != 'installed':
    raise RuntimeError('acceptance product seed is not installed')
if states.get('smart_construction_acceptance_fixture') != 'installed':
    raise RuntimeError('acceptance fixture carrier is not installed')
if states.get('smart_construction_demo') == 'installed':
    raise RuntimeError('acceptance module set must not install smart_construction_demo')
print('[frontend.acceptance.ensure] product_base_keys=%s states=%s' % (param, states))
PY

echo "[db.frontend.acceptance.ensure] PASS db=${DB_NAME}"
