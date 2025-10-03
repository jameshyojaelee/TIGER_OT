#!/bin/bash
# Compatibility wrapper. New location: scripts/01b_create_conda_env.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "${SCRIPT_DIR}/scripts/01b_create_conda_env.sh" "$@"
