#!/bin/bash
set -e

apt update
apt install -y nginx openssh-server

systemctl enable ssh
systemctl start ssh
