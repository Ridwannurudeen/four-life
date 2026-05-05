#!/bin/bash
# FOUR-LIFE VPS deployment script.
# Intended to be rerun — every step is idempotent.
set -euo pipefail

REPO_URL="https://github.com/Ridwannurudeen/four-life.git"
REPO_DIR="/opt/four-life"
WEB_DIR="$REPO_DIR/web"
DOMAIN="four-life.gudman.xyz"
RUN_USER="fourlife"

echo "=== FOUR-LIFE Deployment ==="

# 0. Dedicated service account (no shell, no home)
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$RUN_USER"
fi

# 1. Source
if [ -d "$REPO_DIR/.git" ]; then
    cd "$REPO_DIR"
    git pull
else
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

# 2. Python deps
# The VPS runs the API from system Python. Newer Debian/Ubuntu releases enforce
# PEP 668 for system installs, so allow this deployment-managed environment.
PIP_BREAK_SYSTEM_PACKAGES=1 pip3 install -r requirements.txt --quiet

# 3. Data dirs for SQLite + memory snapshots (writable by the service user)
mkdir -p data/logs data/memory
chown -R "$RUN_USER:$RUN_USER" "$REPO_DIR/data"

# 4. Systemd service for the API
install -m 644 deploy/four-life.service /etc/systemd/system/four-life.service
systemctl daemon-reload
systemctl enable four-life
systemctl restart four-life

# 5. Next.js static export for the frontend.
#    `npm ci` gives reproducible installs; production-only is wrong here because
#    the build toolchain (next, typescript, eslint-config-next) lives in devDeps.
cd "$WEB_DIR"
npm ci
npm run build
# Next emits the static site to web/out/ (configured in next.config.ts). nginx
# serves from there directly — there is no Next server to proxy.

# 6. Nginx site
install -m 644 "$REPO_DIR/deploy/nginx.conf" /etc/nginx/sites-available/four-life
ln -sf /etc/nginx/sites-available/four-life /etc/nginx/sites-enabled/four-life
nginx -t
systemctl reload nginx

# 7. SSL cert via webroot (never --nginx, which rewrites listeners and breaks SNI)
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    certbot certonly --webroot -w /var/www/html -d "$DOMAIN" --non-interactive \
        --agree-tos --register-unsafely-without-email \
        || echo "SSL cert issuance failed — run certbot manually"
fi

echo "=== FOUR-LIFE deployed ==="
echo "API:       https://$DOMAIN/api/status"
echo "Dashboard: https://$DOMAIN"
echo "Docs:      https://$DOMAIN/docs"
