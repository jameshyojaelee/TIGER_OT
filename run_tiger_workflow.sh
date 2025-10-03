#!/bin/bash
# Compatibility wrapper. New location: scripts/04_run_workflow.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
exec "${SCRIPT_DIR}/scripts/04_run_workflow.sh" "$@"
