#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/dist/CNCDFMApp-bundled.app"

if [[ ! -d "${APP_DIR}" ]]; then
  echo "Bundled app not found at ${APP_DIR}" >&2
  echo "Run ./Scripts/build-bundled-app.sh first." >&2
  exit 1
fi

open "${APP_DIR}"
