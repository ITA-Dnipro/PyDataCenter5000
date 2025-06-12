#!/bin/bash
set -e

# Install Nginx
sudo apt-get update
sudo apt-get install -y nginx

# Configure Nginx as reverse proxy
cat << EOF | sudo tee /etc/nginx/sites-available/fastapi
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

# Enable the site and restart Nginx
sudo ln -sf /etc/nginx/sites-available/fastapi /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
