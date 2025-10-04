#!/bin/bash
# Compatibility wrapper. New location: scripts/01b_create_conda_env.sh
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
exec "${SCRIPTS_DIR}/01b_create_conda_env.sh" "$@"
