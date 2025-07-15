#!/bin/bash
set -e

# Install NTP package
apt update
apt install -y ntp

# Backup default pool entries and add custom server
sed -i 's/^pool /# pool /g' /etc/ntp.conf
echo "server 0.ubuntu.pool.ntp.org iburst" | tee -a /etc/ntp.conf

systemctl enable ntp
