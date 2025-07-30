#!/bin/bash
set -e

apt update
apt install -y nginx openssh-server curl

systemctl enable ssh
