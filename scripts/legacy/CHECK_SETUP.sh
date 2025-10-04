#!/bin/bash
# Compatibility wrapper. New location: scripts/02_quick_check.sh
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
exec "${SCRIPTS_DIR}/02_quick_check.sh" "$@"
