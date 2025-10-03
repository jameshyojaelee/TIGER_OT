#!/bin/bash
# Simple entrypoint that configures the TIGER environment and launches the workflow.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ "$#" -lt 1 ]; then
  cat <<USAGE
Usage: $(basename "$0") targets.txt [workflow options]

Runs the Cas13 TIGER workflow with the provided targets file.
Any additional arguments are forwarded to run_tiger.py.
USAGE
  exit 1
fi

exec "${SCRIPT_DIR}/run_with_tiger_env.sh" python3 "${SCRIPT_DIR}/run_tiger.py" "$@"
