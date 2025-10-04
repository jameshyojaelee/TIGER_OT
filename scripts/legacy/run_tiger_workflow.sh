#!/bin/bash
# Compatibility wrapper. New location: scripts/04_run_workflow.sh
SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
exec "${SCRIPTS_DIR}/04_run_workflow.sh" "$@"
