#!/bin/bash
set -e

apt-get update
apt-get install -y postfix mailutils

cat > /etc/postfix/main.cf <<'EOF'
myhostname = smtp.local
myorigin = /etc/mailname
mydestination = $myhostname, localhost.$mydomain, localhost
relayhost =
mynetworks = 127.0.0.0/8
mailbox_size_limit = 0
recipient_delimiter = +
EOF

systemctl enable postfix
