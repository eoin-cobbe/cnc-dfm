#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/dist/CNCDFMApp-bundled.app"
BACKEND_DIR="${APP_DIR}/Contents/Resources/backend"
PYTHON_BIN="${BACKEND_DIR}/.conda-env/bin/python"
API_SCRIPT="${BACKEND_DIR}/src/dfm_app_api.py"

if [[ ! -x "${PYTHON_BIN}" || ! -f "${API_SCRIPT}" ]]; then
  echo "Bundled backend not found. Run ./Scripts/build-bundled-app.sh first." >&2
  exit 1
fi

"${PYTHON_BIN}" "${API_SCRIPT}" health
