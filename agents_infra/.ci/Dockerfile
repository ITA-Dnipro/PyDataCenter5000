FROM ubuntu:20.04

ARG RUN_TESTS=true

RUN apt update && \
    apt install -y ruby ruby-dev build-essential ansible rsync sudo

RUN gem install dotenv -v 2.8.1
RUN gem install --no-document fpm -v 1.15.1

WORKDIR /workspace
COPY . /workspace

RUN ansible-playbook playbooks/install.yaml -l local \
     -e "run_tests=${RUN_TESTS} fail_if_dep_missing=true"
