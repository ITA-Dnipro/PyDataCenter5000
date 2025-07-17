#!/bin/bash
set -e

SSH_PASSWORD="$1"

mkdir /var/run/sshd
echo "root:${SSH_PASSWORD}" | chpasswd
sed -i 's/.*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

echo "cd /app" >> /root/.bashrc