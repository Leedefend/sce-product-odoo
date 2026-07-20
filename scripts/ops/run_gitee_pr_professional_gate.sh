#!/usr/bin/env bash
set -euo pipefail
readonly sha="e2c6aebca5a702ab273081e9fe2c154391155da7"
readonly pr="2"
[ "${GITEE_PR_PROFESSIONAL_CONFIRM:-}" = "1" ] || { echo "confirmation required" >&2; exit 2; }
ssh -o BatchMode=yes root@1.95.2.123 \
 "systemd-run --quiet --wait --pipe --collect --unit=gitee-pr-2-professional --uid=gitee-ci --gid=gitee-ci --property=SupplementaryGroups=gitee-mirror-source --property=EnvironmentFile=/etc/gitee-ci/sce-product-odoo-worker.env /opt/gitee-ci/sce-product-odoo/gitee_ci_run.sh '${sha}' merge_request_hooks '${pr}'"
