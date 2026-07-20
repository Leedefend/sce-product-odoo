#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export ROOT_DIR
source "$ROOT_DIR/scripts/common/env.sh"
source "$ROOT_DIR/scripts/common/guard_prod.sh"
source "$ROOT_DIR/scripts/common/compose.sh"
source "$ROOT_DIR/scripts/common/demo_data_guard.sh"
guard_prod_forbid
guard_demo_data_scope

: "${DB_NAME:?DB_NAME is required}"
selected="${STEPS:-${PROFILE:+profile:${PROFILE}}}"
: "${selected:?STEPS or PROFILE is required}"

export DB_NAME SC_ENVIRONMENT SC_ALLOW_DEMO_DATA SC_DEMO_USER_PASSWORD selected
compose_dev run --rm -T \
  -e DB_NAME \
  -e SC_ENVIRONMENT \
  -e SC_ALLOW_DEMO_DATA \
  -e SC_DEMO_USER_PASSWORD \
  -e selected \
  --entrypoint /usr/bin/odoo odoo \
  shell --config="$ODOO_CONF" \
  -d "$DB_NAME" \
  --db_host=db --db_port=5432 --db_user="$DB_USER" --db_password="$DB_PASSWORD" \
  --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/source-addons,/mnt/extra-addons,"$ADDONS_EXTERNAL_MOUNT" \
  --no-http --workers=0 --max-cron-threads=0 \
<<'PY'
import os
from odoo.addons.smart_construction_demo.seed import run_steps

executed = run_steps(env, os.environ["selected"])
env.cr.commit()
print("[demo.seed] executed=%s" % ",".join(executed))
PY
