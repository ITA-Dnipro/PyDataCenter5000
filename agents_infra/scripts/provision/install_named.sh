#!/bin/bash
set -e

# Set up DNS server
apt update
apt install -y bind9 bind9utils bind9-doc dnsutils

# Configure DNS named.conf.options
cat > /etc/bind/named.conf.options << 'EOF'
# Restrict queries to localhost and internal subnet for security. Adjust as needed for your environment.
options {
    directory "/var/cache/bind";

    recursion yes;
    allow-query { localhost; 192.168.0.0/16; };

    forwarders {
        8.8.8.8;
        1.1.1.1;
    };

    dnssec-validation auto;
};
EOF

systemctl enable named || true
