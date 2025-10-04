#!/bin/bash
# Compatibility wrapper. New location: scripts/01_setup_workspace.sh
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
exec "${SCRIPTS_DIR}/01_setup_workspace.sh" "$@"
