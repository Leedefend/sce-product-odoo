#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
echo "[deprecated] use scripts/test/frontend_productization_fixture.sh" >&2
exec "$ROOT_DIR/scripts/test/frontend_productization_fixture.sh" "$@"
