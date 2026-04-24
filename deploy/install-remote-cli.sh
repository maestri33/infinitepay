#!/usr/bin/env bash
# Compatibility wrapper for the root one-line installer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$SCRIPT_DIR/install_cli.sh" "$@"
