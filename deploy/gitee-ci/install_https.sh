#!/usr/bin/env bash
set -euo pipefail

readonly public_ip="1.95.2.123"
readonly cert_name="gitee-ci-1-95-2-123"
readonly webroot="/var/www/gitee-ci-acme"

if [ "$(id -u)" -ne 0 ]; then
  echo "[gitee_ci_https] root is required" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends nginx snapd
snap install core >/dev/null 2>&1 || snap refresh core
if ! snap list certbot >/dev/null 2>&1; then
  snap install --classic certbot
else
  snap refresh certbot
fi
ln -sfn /snap/bin/certbot /usr/local/bin/certbot

certbot_version="$(certbot --version 2>&1 | awk '{print $2}')"
certbot_major="${certbot_version%%.*}"
if ! [[ "${certbot_major}" =~ ^[0-9]+$ ]] || [ "${certbot_major}" -lt 5 ]; then
  echo "[gitee_ci_https] certbot 5.4 or newer is required" >&2
  exit 2
fi

install -d -o www-data -g www-data -m 0755 "${webroot}/.well-known/acme-challenge"
cat > /etc/nginx/sites-available/gitee-ci-http <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${public_ip};

    location ^~ /.well-known/acme-challenge/ {
        root ${webroot};
        default_type text/plain;
    }

    location / {
        return 404;
    }
}
EOF
ln -sfn /etc/nginx/sites-available/gitee-ci-http /etc/nginx/sites-enabled/gitee-ci-http
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if [ ! -s "/etc/letsencrypt/live/${cert_name}/fullchain.pem" ]; then
  certbot certonly \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email \
    --preferred-profile shortlived \
    --webroot \
    --webroot-path "${webroot}" \
    --ip-address "${public_ip}" \
    --cert-name "${cert_name}"
fi
rm -f "${webroot}/.well-known/acme-challenge/codex-probe"

cat > /etc/nginx/conf.d/gitee-ci-rate-limit.conf <<'EOF'
limit_req_zone $binary_remote_addr zone=gitee_ci_webhook:10m rate=30r/m;
EOF
cat > /etc/nginx/sites-available/gitee-ci-https <<EOF
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name ${public_ip};

    ssl_certificate /etc/letsencrypt/live/${cert_name}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${cert_name}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_tickets off;
    client_max_body_size 1m;

    location = /hooks/gitee {
        # Gitee's API-created signing WebHook puts its ephemeral signature in
        # the query string. The receiver validates it; Nginx must not log it.
        access_log off;
        limit_except POST { deny all; }
        limit_req zone=gitee_ci_webhook burst=10 nodelay;
        proxy_pass http://127.0.0.1:9080;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_connect_timeout 3s;
        proxy_send_timeout 10s;
        proxy_read_timeout 10s;
    }

    location = /healthz {
        proxy_pass http://127.0.0.1:9080;
        proxy_connect_timeout 3s;
        proxy_read_timeout 3s;
    }

    location / {
        return 404;
    }
}
EOF
ln -sfn /etc/nginx/sites-available/gitee-ci-https /etc/nginx/sites-enabled/gitee-ci-https

install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-gitee-ci-nginx <<'EOF'
#!/usr/bin/env sh
set -eu
/usr/sbin/nginx -t
/bin/systemctl reload nginx
EOF
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/reload-gitee-ci-nginx

nginx -t
systemctl reload nginx
echo "[gitee_ci_https] PASS url=https://${public_ip}/hooks/gitee certbot=${certbot_version}"
