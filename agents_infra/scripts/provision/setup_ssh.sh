#!/bin/bash
set -e

mkdir -p /var/run/sshd

# Ensure a dedicated non-root user 'user' exists for SSH access
if ! id -u user >/dev/null 2>&1; then
    useradd -m -s /bin/bash user
fi

# Set the SSH password for 'user' from the Docker secret
PW=$(cat /run/secrets/ssh_password)
echo "user:$PW" | chpasswd

# Harden SSH configuration: disable root login, enable password authentication
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i '/^\s*account\s\+required\s\+pam_nologin\.so/s/^/#/' /etc/pam.d/sshd

# Set the default working directory for 'user' upon SSH login
echo "cd /app" >> /home/user/.bashrc
chown user:user /home/user/.bashrc

exec /sbin/init
