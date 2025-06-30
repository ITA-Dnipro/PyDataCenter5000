#!/bin/bash
set -e

# Install Nginx if not already installed
if ! dpkg -l | grep -q nginx; then
    sudo apt-get update
    sudo apt-get install -y nginx
else
    echo "[INFO] Nginx already installed."
fi

# Configure Nginx as reverse proxy only if config differs
NGINX_CONF="/etc/nginx/sites-available/fastapi"
NEW_CONF="/tmp/fastapi_nginx_conf.tmp"

cat << EOF > "$NEW_CONF"
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$http_host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_redirect off;
        proxy_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

if ! cmp -s "$NEW_CONF" "$NGINX_CONF"; then
    sudo cp "$NEW_CONF" "$NGINX_CONF"
    sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t
    sudo systemctl reload nginx
    echo "[INFO] Nginx config updated and reloaded."
else
    echo "[INFO] Nginx config unchanged."
fi
rm -f "$NEW_CONF"
