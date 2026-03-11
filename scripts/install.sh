#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "${ROOT_DIR}/scripts/install.py"
fi

if command -v python >/dev/null 2>&1; then
  exec python "${ROOT_DIR}/scripts/install.py"
fi

echo "python3 is required to run the installer."
exit 1
