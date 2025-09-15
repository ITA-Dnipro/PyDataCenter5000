#!/bin/bash
set -e

: "${RUN_TESTS:=false}"
: "${FAIL_IF_DEP_MISSING:=false}"

ansible-playbook playbooks/main.yaml \
    -l local \
    -e "run_tests=${RUN_TESTS} \
    fail_if_dep_missing=${FAIL_IF_DEP_MISSING}"
