#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/dist/CNCDFMApp-bundled.app"
TEST_DIR="/tmp/cncdfm-bundled-smoke"
TEST_APP="${TEST_DIR}/CNCDFMApp-bundled.app"
PYTHON_BIN="${TEST_APP}/Contents/Resources/backend/.conda-env/bin/python"
API_SCRIPT="${TEST_APP}/Contents/Resources/backend/src/dfm_app_api.py"

if [[ ! -d "${APP_DIR}" ]]; then
  echo "Bundled app not found at ${APP_DIR}" >&2
  echo "Run ./Scripts/build-bundled-app.sh first." >&2
  exit 1
fi

rm -rf "${TEST_DIR}"
mkdir -p "${TEST_DIR}"
rsync -a "${APP_DIR}" "${TEST_DIR}/"
"${PYTHON_BIN}" "${API_SCRIPT}" health
