FROM ubuntu:18.04

COPY ../scripts/config.env /tmp/config.env
COPY ../scripts/environment/docker.env /tmp/docker.env
COPY ../scripts/install-dependencies.sh /tmp/install-dependencies.sh

RUN chmod +x /tmp/install-dependencies.sh && \
    /tmp/install-dependencies.sh
