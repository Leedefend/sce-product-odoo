#!/usr/bin/env bash
set -euo pipefail

source_root="${1:?source root is required}"
[ "$(id -u)" -eq 0 ] || { echo "[gitee_mirror_install] root is required" >&2; exit 2; }
test -f "${source_root}/scripts/ops/gitee_to_github_mirror.sh"
test -f "${source_root}/scripts/ci/gitee_ci_run.sh"

getent group gitee-mirror-source >/dev/null || groupadd --system gitee-mirror-source
id gitee-mirror >/dev/null 2>&1 || \
  useradd --system --home-dir /var/lib/gitee-mirror --shell /usr/sbin/nologin gitee-mirror
usermod -a -G gitee-mirror-source gitee-ci
usermod -a -G gitee-mirror-source gitee-mirror

install -d -o root -g root -m 0755 /opt/gitee-mirror
install -d -o gitee-mirror -g gitee-mirror-source -m 0770 /var/lib/gitee-mirror
install -d -o root -g gitee-mirror -m 0750 /etc/gitee-mirror
install -o root -g root -m 0755 \
  "${source_root}/scripts/ops/gitee_to_github_mirror.sh" \
  /opt/gitee-mirror/gitee_to_github_mirror.sh
install -o root -g root -m 0755 \
  "${source_root}/scripts/ci/gitee_ci_run.sh" \
  /opt/gitee-ci/sce-product-odoo/gitee_ci_run.sh

if [ ! -d /var/lib/gitee-mirror/source.git ]; then
  runuser -u gitee-ci -- git init --bare /var/lib/gitee-mirror/source.git >/dev/null
fi
chown -R gitee-ci:gitee-mirror-source /var/lib/gitee-mirror/source.git
chmod -R g+rwX,o-rwx /var/lib/gitee-mirror/source.git
runuser -u gitee-ci -- git --git-dir=/var/lib/gitee-mirror/source.git config receive.denyNonFastForwards true
runuser -u gitee-ci -- git --git-dir=/var/lib/gitee-mirror/source.git config receive.denyDeletes true
chown gitee-ci:gitee-mirror-source /var/lib/gitee-mirror/source.git/config
chmod 0660 /var/lib/gitee-mirror/source.git/config

if [ ! -f /etc/gitee-mirror/github_ed25519 ]; then
  ssh-keygen -q -t ed25519 -N '' -C 'sce-gitee-to-github-mirror' \
    -f /etc/gitee-mirror/github_ed25519
fi
chown root:gitee-mirror /etc/gitee-mirror/github_ed25519
chown root:root /etc/gitee-mirror/github_ed25519.pub
chmod 0440 /etc/gitee-mirror/github_ed25519
chmod 0444 /etc/gitee-mirror/github_ed25519.pub
printf '%s\n' \
  'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' \
  > /etc/gitee-mirror/github_known_hosts
chown root:gitee-mirror /etc/gitee-mirror/github_known_hosts
chmod 0440 /etc/gitee-mirror/github_known_hosts

worker_env=/etc/gitee-ci/sce-product-odoo-worker.env
test -f "${worker_env}"
if ! grep -q '^GITEE_MIRROR_SOURCE_REPO=' "${worker_env}"; then
  printf '%s\n' 'GITEE_MIRROR_SOURCE_REPO=/var/lib/gitee-mirror/source.git' >> "${worker_env}"
fi

install -o root -g root -m 0644 \
  "${source_root}/deploy/gitee-mirror/gitee-to-github-mirror.service" \
  /etc/systemd/system/gitee-to-github-mirror.service
install -o root -g root -m 0644 \
  "${source_root}/deploy/gitee-mirror/gitee-to-github-mirror.timer" \
  /etc/systemd/system/gitee-to-github-mirror.timer
systemctl daemon-reload
systemctl enable gitee-to-github-mirror.timer
systemctl reset-failed gitee-to-github-mirror.service || true
systemctl restart gitee-ci-worker.service

echo "[gitee_mirror_install] PASS github deploy key follows (public key only):"
cat /etc/gitee-mirror/github_ed25519.pub
