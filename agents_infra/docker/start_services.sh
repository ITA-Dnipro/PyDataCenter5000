#!/bin/bash
set -e

echo "[INFO] Starting container services..."

# Start systemd
/sbin/init &

# Wait for systemd to be ready
sleep 10

# Check if main.py exists
if [ ! -f /app/server/main.py ]; then
    echo "ERROR: main.py not found in /app/server/"
    ls -la /app/server/
    exit 1
fi

# Test if gunicorn can start
echo "[INFO] Testing gunicorn startup..."
cd /app/server
/opt/fastapi/venv/bin/gunicorn --check-config main:app -k uvicorn.workers.UvicornWorker || {
    echo "ERROR: Gunicorn config check failed"
    exit 1
}

# Reload systemd and start services
systemctl daemon-reload
systemctl start nginx
systemctl start fastapi

# Check service status
sleep 3
systemctl status nginx --no-pager
systemctl status fastapi --no-pager

echo "[INFO] Services started successfully. Monitoring..."

# Keep container running and monitor services
while true; do
    if ! systemctl is-active --quiet fastapi; then
        echo "WARNING: FastAPI service failed, checking logs..."
        journalctl -u fastapi --no-pager -n 20
        systemctl restart fastapi
    fi
    if ! systemctl is-active --quiet nginx; then
        echo "WARNING: Nginx service failed, restarting..."
        systemctl restart nginx
    fi
    sleep 30
done
