FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHON_DIR=/opt/python2.6.9
ENV INSTALL_CORO=true

RUN apt update && \
    apt install -y ansible rsync sudo

WORKDIR /workspace

COPY . /workspace

RUN ansible-playbook -i "localhost," playbooks/install.yaml -c local
