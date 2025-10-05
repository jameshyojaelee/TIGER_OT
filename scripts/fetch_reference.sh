#!/usr/bin/env bash
# Helper to download reference transcriptomes via the shared tiger_guides CLI
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
export PYTHONPATH="${ROOT_DIR}/tiger_guides_pkg/src:${PYTHONPATH:-}"

if [ "$#" -lt 1 ]; then
  echo "Usage: scripts/fetch_reference.sh <species> [destination]" >&2
  exit 1
fi

SPECIES="$1"
DESTINATION="${2:-${ROOT_DIR}/resources/reference}"

exec "${ROOT_DIR}/scripts/00_load_environment.sh" python3 -m tiger_guides.cli fetch-reference --species "$SPECIES" --destination "$DESTINATION"
