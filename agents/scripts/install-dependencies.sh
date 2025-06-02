#!/bin/bash
set -e

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

set -a
source "$scripts_dir/config.env"
source "$scripts_dir/${ENV_FILE}"
set +a

echo "[INFO] Updating and installing system packages..."
apt-get clean && rm -rf /var/lib/apt/lists/* && apt-get update
apt-get install -y build-essential zlib1g-dev wget git

if [ "$INSTALL_FFI" = "true" ]; then
    apt-get install -y libffi-dev
fi

if [ "$INSTALL_NCURSES" = "true" ]; then
    apt-get install -y libncurses5-dev
fi

if [ "$INSTALL_GDBM" = "true" ]; then
    apt-get install -y libgdbm-dev
fi

if [ "$INSTALL_OPEN_SSL" = "true" ]; then
    apt-get install -y libssl-dev
fi

if [ "$INSTALL_READLINE" = "true" ]; then
    apt-get install -y libreadline-dev
fi

if [ "$INSTALL_SQLITE" = "true" ]; then
    apt-get install -y libsqlite3-dev
fi

mkdir -p /python-build/src
cd /python-build/src

if ! "${PYTHON_DIR}/bin/python" --version > /dev/null 2>&1; then
    mkdir -p python

    if [ ! -f python/python.tar.gz ]; then
        echo "[INFO] Downloading Python 2.6.9..."
        python_url="https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz"
        wget -O python/python.tar.gz ${python_url}
        tar -C python --strip-components 1 -xzf python/python.tar.gz
    fi

    cd python

    if [ "$BUILD_ZLIB_FROM_SRC" = "true" ]; then
        echo "[INFO] Building zlib..."
        cp Modules/Setup.dist Modules/Setup
        sed -i '/zlibmodule\.c/ s/^# *//' Modules/Setup
    fi

    ncores="$(grep ^processor /proc/cpuinfo 2>/dev/null | wc -l | xargs)"
    ncores="${ncores#0}"

    echo "[INFO] Building Python 2.6.9..."
    ./configure --prefix=${PYTHON_DIR}
    make -j"$ncores" && make install
    cd .. && rm -rf python
fi

ln -sf ${PYTHON_DIR}/bin/python /usr/local/bin/python
echo "[INFO] Python version:" && python --version

if ! python -c "import setuptools"; then
    echo "[INFO] Installing setuptools..."
    if [ ! -d setuptools ]; then
        mkdir setuptools
        wget -O setuptools/ez_setup.py https://bootstrap.pypa.io/ez_setup.py
    fi
    python setuptools/ez_setup.py && rm -rf setuptools
fi

if ! python -c "import psutil"; then
    echo "[INFO] Installing psutil..."
    if [ ! -d psutil ]; then
        git clone https://github.com/giampaolo/psutil.git psutil
    fi
    cd psutil
    git checkout release-5.7.0
    python setup.py install
    cd .. && rm -rf psutil
fi

if ! python -c "import argparse"; then
    echo "[INFO] Installing argparse..."
    if [ ! -d argparse ]; then
        mkdir argparse
        argparse_url="https://files.pythonhosted.org/packages/18/dd/e617cfc3f6210ae183374cd9f6a26b20514bbb5a792af97949c5aacddf0f/argparse-1.4.0.tar.gz"
        wget -O argparse/argparse.tar.gz ${argparse_url}
        tar -C argparse --strip-components 1 -xzf argparse/argparse.tar.gz
    fi
    cd argparse
    python setup.py install
    cd .. && rm -rf argparse
fi

if ! python -c "import py"; then
    echo "[INFO] Installing py..."
    if [ ! -d py ]; then
        mkdir py
        py_url="https://files.pythonhosted.org/packages/2a/bc/a1a4a332ac10069b8e5e25136a35e08a03f01fd6ab03d819889d79a1fd65/py-1.4.29.tar.gz"
        wget -O py/py.tar.gz ${py_url}
        tar -C py --strip-components 1 -xzf py/py.tar.gz
    fi
    cd py
    python setup.py install
    cd .. && rm -rf py
fi

if ! python -c "import pytest"; then
    echo "[INFO] Installing pytest..."
    if [ ! -d pytest ]; then
        mkdir pytest
        pytest_url="https://files.pythonhosted.org/packages/07/bc/9ce76df7c91b87467e9fcae153297d88b34591f0379f6ad55781b72c2fd1/pytest-2.8.7.tar.gz"
        wget -O pytest/pytest.tar.gz ${pytest_url}
        tar -C pytest --strip-components 1 -xzf pytest/pytest.tar.gz
    fi
    cd pytest
    python setup.py install
    cd .. && rm -rf pytest
fi

if ! python -c "import mock"; then
    echo "[INFO] Installing mock..."
    if [ ! -d mock ]; then
        mkdir mock
        mock_url="https://files.pythonhosted.org/packages/a2/52/7edcd94f0afb721a2d559a5b9aae8af4f8f2c79bc63fdbe8a8a6c9b23bbe/mock-1.0.1.tar.gz"
        wget -O mock/mock.tar.gz ${mock_url}
        tar -C mock --strip-components 1 -xzf mock/mock.tar.gz
    fi
    cd mock
    python setup.py install
    cd .. && rm -rf mock
fi

echo "[INFO] Setup completed successfully."
echo "[INFO] Cleaning up..."
cd ../.. && rm -rf /python-build/src
