#!/usr/bin/env bash
set -euo pipefail

# Ensure references directory exists
mkdir -p "${TIGER_GUIDES_REFERENCE_DIR:-/references}"

exec "$@"
