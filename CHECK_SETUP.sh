#!/bin/bash
# Compatibility wrapper. New location: scripts/02_quick_check.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "${SCRIPT_DIR}/scripts/02_quick_check.sh" "$@"
