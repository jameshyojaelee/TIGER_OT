#!/bin/bash
# Compatibility wrapper. New location: scripts/00_load_environment.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "${SCRIPT_DIR}/scripts/00_load_environment.sh" "$@"
