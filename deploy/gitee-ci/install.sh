#!/usr/bin/env bash
set -euo pipefail

source_root="${1:?source root is required}"
if [ "$(id -u)" -ne 0 ]; then
  echo "[gitee_ci_install] root is required" >&2
  exit 2
fi
test -f "${source_root}/scripts/ci/gitee_webhook_ci.py"
test -f "${source_root}/scripts/ci/gitee_ci_run.sh"
test -f "${source_root}/deploy/gitee-ci/gitee-webhook-ci.service"

if ! command -v corepack >/dev/null 2>&1; then
  echo "[gitee_ci_install] corepack is required" >&2
  exit 2
fi

if ! id gitee-ci >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/gitee-ci --shell /usr/sbin/nologin gitee-ci
fi
install -d -m 0755 /opt/gitee-ci/sce-product-odoo
install -d -o gitee-ci -g gitee-ci -m 0750 \
  /var/lib/gitee-ci /var/lib/gitee-ci/workspaces /var/lib/gitee-ci/artifacts /var/log/gitee-ci
install -d -o gitee-ci -g gitee-ci -m 0750 /etc/gitee-ci
runuser -u gitee-ci -- env HOME=/var/lib/gitee-ci \
  corepack prepare pnpm@9 --activate >/dev/null

install -o root -g root -m 0755 \
  "${source_root}/scripts/ci/gitee_webhook_ci.py" \
  /opt/gitee-ci/sce-product-odoo/gitee_webhook_ci.py
install -o root -g root -m 0755 \
  "${source_root}/scripts/ci/gitee_ci_run.sh" \
  /opt/gitee-ci/sce-product-odoo/gitee_ci_run.sh
install -o root -g root -m 0644 \
  "${source_root}/deploy/gitee-ci/gitee-webhook-ci.service" \
  /etc/systemd/system/gitee-webhook-ci.service

if [ ! -f /etc/gitee-ci/id_ed25519 ]; then
  ssh-keygen -q -t ed25519 -N '' -C 'gitee-ci@sce-product-odoo' \
    -f /etc/gitee-ci/id_ed25519
fi
chown gitee-ci:gitee-ci /etc/gitee-ci/id_ed25519 /etc/gitee-ci/id_ed25519.pub
chmod 0400 /etc/gitee-ci/id_ed25519
chmod 0444 /etc/gitee-ci/id_ed25519.pub

printf '%s\n' \
  'gitee.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEKxHSJ7084RmkJ4YdEi5tngynE8aZe2uEoVVsB/OvYN' \
  > /etc/gitee-ci/known_hosts
chown root:gitee-ci /etc/gitee-ci/known_hosts
chmod 0440 /etc/gitee-ci/known_hosts

if [ -f /etc/gitee-ci/sce-product-odoo.env ]; then
  secret="$(sed -n 's/^GITEE_WEBHOOK_SECRET=//p' /etc/gitee-ci/sce-product-odoo.env)"
  if [ -z "${secret}" ]; then
    echo "[gitee_ci_install] existing secret is invalid" >&2
    exit 2
  fi
else
  secret="$(openssl rand -hex 32)"
fi
umask 0077
{
  printf '%s\n' \
    'GITEE_ALLOWED_REPOSITORY=leegege/sce-product-odoo' \
    'GITEE_ALLOWED_SENDER=leegege' \
    "GITEE_WEBHOOK_SECRET=${secret}" \
    'GITEE_WEBHOOK_PATH=/hooks/gitee' \
    'GITEE_WEBHOOK_MAX_SKEW_SECONDS=300' \
    'GITEE_CI_BIND=127.0.0.1' \
    'GITEE_CI_PORT=9080' \
    'GITEE_CI_DB=/var/lib/gitee-ci/jobs.sqlite3' \
    'GITEE_CI_LOG_DIR=/var/log/gitee-ci' \
    'GITEE_CI_RUNNER=/opt/gitee-ci/sce-product-odoo/gitee_ci_run.sh' \
    'GITEE_CI_WORKSPACE_ROOT=/var/lib/gitee-ci/workspaces' \
    'GITEE_CI_ARTIFACT_ROOT=/var/lib/gitee-ci/artifacts' \
    'GIT_SSH_COMMAND="/usr/bin/ssh -i /etc/gitee-ci/id_ed25519 -o IdentitiesOnly=yes -o UserKnownHostsFile=/etc/gitee-ci/known_hosts -o StrictHostKeyChecking=yes"'
} > /etc/gitee-ci/sce-product-odoo.env
chown root:gitee-ci /etc/gitee-ci/sce-product-odoo.env
chmod 0440 /etc/gitee-ci/sce-product-odoo.env

systemctl daemon-reload
systemctl enable gitee-webhook-ci.service
systemctl restart gitee-webhook-ci.service
echo "[gitee_ci_install] PASS bind=127.0.0.1:9080 secret=stored-not-printed"
echo "[gitee_ci_install] deploy-key follows (public key only):"
cat /etc/gitee-ci/id_ed25519.pub
