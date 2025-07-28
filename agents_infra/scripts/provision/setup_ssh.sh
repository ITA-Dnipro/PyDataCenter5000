#!/bin/bash
set -e

mkdir -p /var/run/sshd

# Set root password from secret
PW=$(cat /run/secrets/ssh_password)
echo "root:$PW" | chpasswd

# Allow SSH login for root
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Set default directory on login for root
echo "cd /app" >> /root/.bashrc

exec /sbin/init
