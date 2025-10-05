#!/usr/bin/env bash
# Helper to download TIGER model bundles via the shared tiger_guides CLI
set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
export PYTHONPATH="${ROOT_DIR}/tiger_guides_pkg/src:${PYTHONPATH:-}"

MODEL="${1:-tiger}"
DESTINATION="${2:-${ROOT_DIR}}"

if [ -z "${TIGER_MODEL_ARCHIVE:-}" ] && [ -z "${TIGER_MODEL_ARCHIVE_URL:-}" ]; then
  cat >&2 <<'MSG'
No model archive configured.
Set TIGER_MODEL_ARCHIVE to a local tar/zip file or TIGER_MODEL_ARCHIVE_URL to a downloadable archive before running this helper.
MSG
  exit 1
fi

exec "${ROOT_DIR}/scripts/00_load_environment.sh" python3 -m tiger_guides.cli fetch-model --model "$MODEL" --destination "$DESTINATION"
