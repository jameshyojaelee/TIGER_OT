#!/bin/bash
# 04_run_workflow.sh -- launch TIGER workflow with the environment wrapper
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
WRAPPER="${ROOT_DIR}/run_with_tiger_env.sh"
DRIVER="${ROOT_DIR}/run_tiger.py"

if [ "$#" -lt 1 ]; then
  cat <<'USAGE'
Usage: scripts/04_run_workflow.sh targets.txt [workflow options]

Runs the Cas13 TIGER workflow with the provided targets file.
All additional arguments are forwarded to run_tiger.py -- use --help for details.
USAGE
  exit 1
fi

exec "$WRAPPER" python3 "$DRIVER" "$@"
