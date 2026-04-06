#!/bin/bash
# FOUR-LIFE VPS deployment script
set -e

echo "=== FOUR-LIFE Deployment ==="

# Clone or pull
if [ -d /opt/four-life ]; then
    cd /opt/four-life
    git pull
else
    git clone https://github.com/Ridwannurudeen/four-life.git /opt/four-life
    cd /opt/four-life
fi

# Python deps
pip3 install -r requirements.txt --quiet

# Data dirs
mkdir -p data/logs data/memory

# Systemd service
cp deploy/four-life.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable four-life
systemctl restart four-life

# Dashboard
cd web
npm install --production
npm run build
npx next start -p 3030 &

# Nginx
cp deploy/nginx.conf /etc/nginx/sites-available/four-life
ln -sf /etc/nginx/sites-available/four-life /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# SSL cert (webroot only — never use certbot --nginx)
certbot certonly -d four-life.gudman.xyz --non-interactive || echo "SSL cert may need manual setup"

echo "=== FOUR-LIFE deployed ==="
echo "API: https://four-life.gudman.xyz/api/status"
echo "Dashboard: https://four-life.gudman.xyz"
