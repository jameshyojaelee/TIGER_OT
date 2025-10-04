#!/bin/bash
# Compatibility wrapper. New location: scripts/00_load_environment.sh
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
exec "${SCRIPTS_DIR}/00_load_environment.sh" "$@"
