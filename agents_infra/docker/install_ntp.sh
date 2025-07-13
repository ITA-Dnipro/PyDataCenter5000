# Install NTP package
apt update
apt install -y ntp

# Backup default pool entries and add custom server
sed -i 's/^pool /# pool /g' /etc/ntp.conf
echo "server 0.ubuntu.pool.ntp.org iburst" | tee -a /etc/ntp.conf

# Reload systemd, enable and restart NTP service
systemctl daemon-reload
systemctl enable ntp
