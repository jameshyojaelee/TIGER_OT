#!/bin/bash
# Compatibility wrapper. New location: scripts/03_preflight_check.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "${SCRIPT_DIR}/scripts/03_preflight_check.sh" "$@"
