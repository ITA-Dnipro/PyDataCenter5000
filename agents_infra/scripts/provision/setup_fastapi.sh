#!/bin/bash
set -e

echo "[INFO] Setting up FastAPI environment..."

# Create systemd service for FastAPI
echo "[INFO] Creating systemd service..."
cat > /etc/systemd/system/fastapi.service << 'EOF'
[Unit]
Description=FastAPI via Gunicorn
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/app/server
Environment="VIRTUAL_ENV=/opt/fastapi/venv"
Environment="PORT=8000"
ExecStart=/opt/fastapi/venv/bin/gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4 --pythonpath /app/server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl enable fastapi

echo "[INFO] FastAPI setup completed."
