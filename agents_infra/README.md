# Agents Infra

A Linux-based (Debian and ReDHat) server agent infrastructure service.

Servers:

- DNS Server
- SMTP Server
- NTP Server
- Web Server

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)

### For local builds

- Enable paswordless `sudo` (via `visudo`)
- Python 3 (for Ansible build)

## Setting up Agents Infra

Agents Infra supports `.deb` and `.rpm` package artifacts for Debian and RedHat systems, respectively.

### Configuration (optional)

To configure your installation, run

```bash
./configure
```

You will be prompted to set values for configuration parameters such as

- `PYTHON_DIR` (install path for Python 2.6.9)
- `RUN_TESTS` (whether to run unit tests upon installation)

Otherwise, default values will be used.

### Installation

For local installation of Agents Infra, run

```
./install
```

This will build the dependency tree, create package and archive `.zip` artifacts and enable `agents-infra` background service. You can check service status with `systemctl status agents-infra`.

To build Agents Infra in Docker, run

```bash
docker build --platform linux/amd64 -t <image-name> -f Dockerfile .
```

Note that **Docker containers typically do not run a full init system** like `systemd`, therefore, the installation steps involving `systemctl` will be skipped.
