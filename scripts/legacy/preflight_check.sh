#!/bin/bash
# Compatibility wrapper. New location: scripts/03_preflight_check.sh
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
exec "${SCRIPTS_DIR}/03_preflight_check.sh" "$@"
