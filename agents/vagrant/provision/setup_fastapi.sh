#!/bin/bash
set -e

# Install python3-venv
sudo apt-get update
sudo apt-get install -y python3-venv

# Create virtual environment in /opt
sudo mkdir -p /opt/fastapi
sudo chown vagrant:vagrant /opt/fastapi
cd /opt/fastapi
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r /home/vagrant/server/requirements.txt

# Create systemd service for FastAPI
sudo tee /etc/systemd/system/fastapi.service << EOF
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

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable fastapi
sudo systemctl start fastapi
