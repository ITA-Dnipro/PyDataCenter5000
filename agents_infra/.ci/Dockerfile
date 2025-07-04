FROM ubuntu:20.04

RUN apt update && \
    apt install -y ansible rsync sudo

WORKDIR /workspace

COPY . /workspace

RUN ansible-playbook -i "localhost," playbooks/install.yaml -c local
