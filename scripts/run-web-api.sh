#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ROOT_DIR}/.conda-env"
PYTHON_BIN="${ENV_DIR}/bin/python"
PORT="${PORT:-8000}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Expected Python runtime at ${PYTHON_BIN}."
  echo "Run ./scripts/install.sh first, then install web extras with:"
  echo "  ${PYTHON_BIN} -m pip install -r ${ROOT_DIR}/requirements-web.txt"
  exit 1
fi

exec "${PYTHON_BIN}" -m uvicorn dfm_web_api:app --app-dir "${ROOT_DIR}/src" --host 0.0.0.0 --port "${PORT}" --reload
