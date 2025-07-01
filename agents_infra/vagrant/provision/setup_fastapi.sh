#!/bin/bash
set -e

# Install python3-venv if not already installed
if ! dpkg -l | grep -q python3-venv; then
    sudo apt-get update
    sudo apt-get install -y python3-venv
else
    echo "[INFO] python3-venv already installed."
fi

# Create virtual environment in /opt if not present
if [ ! -d /opt/fastapi/venv ]; then
    sudo mkdir -p /opt/fastapi
    sudo chown vagrant:vagrant /opt/fastapi
    cd /opt/fastapi
    python3 -m venv venv
    source venv/bin/activate
    pip install -r /home/vagrant/server/requirements.txt
else
    echo "[INFO] Python venv already exists."
fi

# Create systemd service for FastAPI only if changed
SERVICE_FILE="/etc/systemd/system/fastapi.service"
NEW_SERVICE="/tmp/fastapi_service.tmp"

cat << EOF > "$NEW_SERVICE"
[Unit]
Description=FastAPI via Gunicorn
After=network.target

[Service]
User=vagrant
WorkingDirectory=/home/vagrant/server
Environment="PATH=/opt/fastapi/venv/bin"
Environment="VIRTUAL_ENV=/opt/fastapi/venv"
Environment="PORT=${PORT}"
ExecStart=/opt/fastapi/venv/bin/gunicorn main:app \\
  -k uvicorn.workers.UvicornWorker \\
  --bind 0.0.0.0:\${PORT} \\
  --workers $(nproc) \\
  --pythonpath /home/vagrant/server
Restart=always
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

RELOAD_SERVICE=0
if [ ! -f "$SERVICE_FILE" ] || ! cmp -s "$NEW_SERVICE" "$SERVICE_FILE"; then
    sudo cp "$NEW_SERVICE" "$SERVICE_FILE"
    RELOAD_SERVICE=1
    echo "[INFO] fastapi.service updated."
else
    echo "[INFO] fastapi.service unchanged."
fi
rm -f "$NEW_SERVICE"

if [ $RELOAD_SERVICE -eq 1 ]; then
    sudo systemctl daemon-reload
    sudo systemctl enable fastapi
    sudo systemctl restart fastapi
else
    echo "[INFO] fastapi.service not restarted."
fi
