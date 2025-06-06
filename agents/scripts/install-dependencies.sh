#!/bin/bash
set -e

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

set -a
if [ -f "$scripts_dir/config.env" ]; then
    source "$scripts_dir/config.env"
fi

if [ -z "$ENV_FILE" ]; then
    echo "[WARN] $ENV_FILE is not set - falling back to default values."
else
    if [ ! -f "$scripts_dir/${ENV_FILE}" ]; then
        echo "[WARN] Environment file ${ENV_FILE} not found in ${scripts_dir}."
    else
        source "$scripts_dir/${ENV_FILE}"
    fi
fi
set +a

# Set defaults if not set
: "${INSTALL_FFI:=false}"
: "${INSTALL_NCURSES:=false}"
: "${INSTALL_GDBM:=false}"
: "${INSTALL_OPEN_SSL:=false}"
: "${INSTALL_READLINE:=false}"
: "${INSTALL_SQLITE:=false}"
: "${PYTHON_DIR:=/opt/python2.6}"
: "${BUILD_ZLIB_FROM_SRC:=true}"

get_package_src_from_tar() {
    local name=$1
    local url=$2

    local tarfile="${name}.tar.gz"

    mkdir -p "${name}"
    if [ ! -f "${name}/${tarfile}" ]; then
        echo "[INFO] Downloading ${name} from ${url}..."
        wget -O "${name}/${tarfile}" "${url}"
        tar -C "${name}" --strip-components 1 -xzf "${name}/${tarfile}"
    fi
}

get_package_src_from_git() {
    local name=$1
    local url=$2
    local tag=$3

    git clone "${url}" "${name}"

    if [ -n "${tag}" ]; then
        echo "[INFO] Checking out tag ${tag} for ${name}..."
        cd "${name}"
        git checkout "${tag}"
        cd ..
    fi
}

install_python_package_from_src() {
    local src=$1

    cd "${src}"
    if [ -f setup.py ]; then
        echo "[INFO] Installing Python package from source in ${src}..."
        python setup.py install
        cd .. && rm -rf "${src}"
    fi
}

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
    get_package_src_from_tar python "https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz"

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
    get_package_src_from_git psutil "https://github.com/giampaolo/psutil.git" "release-5.7.0"
    install_python_package_from_src psutil
fi

if ! python -c "import argparse"; then
    get_package_src_from_tar argparse "https://files.pythonhosted.org/packages/18/dd/e617cfc3f6210ae183374cd9f6a26b20514bbb5a792af97949c5aacddf0f/argparse-1.4.0.tar.gz"
    install_python_package_from_src argparse
fi

if ! python -c "import py"; then
    get_package_src_from_tar py "https://files.pythonhosted.org/packages/2a/bc/a1a4a332ac10069b8e5e25136a35e08a03f01fd6ab03d819889d79a1fd65/py-1.4.29.tar.gz"
    install_python_package_from_src py
fi

if ! python -c "import pytest"; then
    get_package_src_from_tar pytest "https://files.pythonhosted.org/packages/07/bc/9ce76df7c91b87467e9fcae153297d88b34591f0379f6ad55781b72c2fd1/pytest-2.8.7.tar.gz"
    install_python_package_from_src pytest
fi

if ! python -c "import mock"; then
    get_package_src_from_tar mock "https://files.pythonhosted.org/packages/a2/52/7edcd94f0afb721a2d559a5b9aae8af4f8f2c79bc63fdbe8a8a6c9b23bbe/mock-1.0.1.tar.gz"
    install_python_package_from_src mock
fi

if ! python -c "import attr"; then
    get_package_src_from_tar attr "https://files.pythonhosted.org/packages/8b/76/c57eefda827b981135ccacd4328fceaa3693f79d9da1e5d78fbe59ebd0c4/attrs-15.2.0.tar.gz"
    install_python_package_from_src attr
fi

if ! python -c "import six"; then
    get_package_src_from_tar six "https://files.pythonhosted.org/packages/16/d8/bc6316cf98419719bd59c91742194c111b6f2e85abac88e496adefaf7afe/six-1.11.0.tar.gz"
    install_python_package_from_src six
fi

if ! python -c "import dateutil"; then
    get_package_src_from_tar dateutil "https://files.pythonhosted.org/packages/54/bb/f1db86504f7a49e1d9b9301531181b00a1c7325dc85a29160ee3eaa73a54/python-dateutil-2.6.1.tar.gz"
    install_python_package_from_src dateutil
fi

echo "[INFO] Setup completed successfully."
echo "[INFO] Cleaning up build directories..."
rm -rf /python-build/src
