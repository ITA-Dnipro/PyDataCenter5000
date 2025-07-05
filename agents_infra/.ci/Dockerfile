FROM ubuntu:20.04

ARG RUN_TESTS=true

RUN apt update && \
    apt install -y ansible rsync sudo

WORKDIR /workspace
COPY . /workspace

RUN ansible-galaxy collection install community.general \
    -c /workspace/playbooks/ansible.cfg

RUN ansible-playbook -i hosts \
    playbooks/install.yaml \
    -l local -e run_tests=true
