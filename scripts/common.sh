#!/bin/bash
set -e

echo "[INFO] Updating and installing system packages..."
apt update
apt install -y nginx openssh-server

systemctl enable ssh
systemctl start ssh

apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
                    libnss3-dev libssl-dev libreadline-dev libffi-dev wget \
                    libsqlite3-dev git

# Installing Python 2.6
if ! /opt/python2.6/bin/python2.6 --version > /dev/null 2>&1; then
    echo "[INFO] Installing Python 2.6.9..."
    cd /usr/src
    wget https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz
    tar xzf Python-2.6.9.tgz

    # Set up and installing zlib
    cd Python-2.6.9/Modules
    cp Setup.dist Setup
    sed -i '/zlibmodule\.c/ s/^# *//' Setup
    cd ..
    ./configure --prefix=/opt/python2.6
    make
    make install
    cd ..
    rm -rf Python-2.6.9 Python-2.6.9.tgz
fi

echo "[INFO] Python 2.6 version:"
/opt/python2.6/bin/python2.6 --version

# ln -sf /opt/python2.6/bin/python2.6 /usr/local/bin/python2
echo 'alias python2="/opt/python2.6/bin/python2.6"' >> ~/.bashrc
source ~/.bashrc


# Instaling setuptools
echo "[INFO] Installing setuptools..."
wget https://bootstrap.pypa.io/ez_setup.py
python2 ez_setup.py
rm ez_setup.py

# Instaling psutil
echo "[INFO] Installing psutil 5.7.0..."
git clone https://github.com/giampaolo/psutil.git
cd psutil
git checkout release-5.7.0
python2 setup.py install
cd ..
rm -rf psutil

if ! /usr/local/bin/python2 -c "import psutil"; then
    echo "[ERROR] psutil failed to install!" >&2
    exit 1
fi

echo "[INFO] Setup completed successfully."
