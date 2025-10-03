#!/bin/bash
# Compatibility wrapper. New location: scripts/01_setup_workspace.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "${SCRIPT_DIR}/scripts/01_setup_workspace.sh" "$@"
