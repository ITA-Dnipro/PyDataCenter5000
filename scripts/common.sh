#!/bin/bash
set -e

echo "[INFO] Updating and installing system packages..."
sudo apt update
sudo apt install -y nginx openssh-server

sudo systemctl enable ssh
sudo systemctl start ssh

sudo apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
                    libnss3-dev libssl-dev libreadline-dev libffi-dev wget \
                    libsqlite3-dev git

# Installing Python 2.6
if ! /opt/python2.6/bin/python2.6 --version > /dev/null 2>&1; then
    echo "[INFO] Installing Python 2.6.9..."
    cd /usr/src
    sudo wget https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz
    sudo tar xzf Python-2.6.9.tgz

    # Set up and installing zlib
    cd Python-2.6.9/Modules
    sudo cp Setup.dist Setup
    sudo sed -i '/zlibmodule\.c/ s/^# *//' Setup
    cd ..
    sudo ./configure --prefix=/opt/python2.6
    sudo make
    sudo make install
    cd ..
    sudo rm -rf Python-2.6.9 Python-2.6.9.tgz
fi

echo "[INFO] Python 2.6 version:"
/opt/python2.6/bin/python2.6 --version

sudo ln -sf /opt/python2.6/bin/python2.6 /usr/local/bin/python2

# Instaling setuptools
echo "[INFO] Installing setuptools..."
wget https://bootstrap.pypa.io/ez_setup.py
sudo python2 ez_setup.py
rm ez_setup.py

# Instaling psutil
echo "[INFO] Installing psutil 5.7.0..."
git clone https://github.com/giampaolo/psutil.git
cd psutil
git checkout release-5.7.0
sudo python2 setup.py install
cd ..
rm -rf psutil

echo "[INFO] Setup completed successfully."
