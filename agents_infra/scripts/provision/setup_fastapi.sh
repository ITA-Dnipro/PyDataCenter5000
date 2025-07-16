#!/bin/bash
set -e

echo "[INFO] Setting up FastAPI environment..."

# Install python3-venv
if ! dpkg -l | grep -q python3-venv; then
    apt-get update
    apt-get install -y python3-venv
    rm -rf /var/lib/apt/lists/*
else
    echo "[INFO] python3-venv already installed."
fi

# Create virtual environment in /opt
if [ ! -d /opt/fastapi/venv ]; then
    mkdir -p /opt/fastapi
    python3 -m venv /opt/fastapi/venv
    /opt/fastapi/venv/bin/pip install --upgrade pip setuptools wheel
    echo "[INFO] Virtual environment created."
else
    echo "[INFO] Python venv already exists."
fi

# Install core dependencies
echo "[INFO] Installing core FastAPI dependencies..."
/opt/fastapi/venv/bin/pip install gunicorn uvicorn[standard] fastapi

# Install project requirements
if [ -f /tmp/requirements.txt ]; then
    echo "[INFO] Installing project requirements..."
    /opt/fastapi/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
    rm /tmp/requirements.txt
fi

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
