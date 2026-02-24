#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ROOT_DIR}/.conda-env"
PYTHON_BIN="${ENV_DIR}/bin/python"

if [[ $# -lt 1 ]]; then
  echo "Usage: ./run /path/to/file.step [extra dfm args]"
  exit 1
fi

STEP_FILE="$1"
shift

if [[ ! -f "${STEP_FILE}" ]]; then
  echo "STEP file not found: ${STEP_FILE}"
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  mamba create -y -p "${ENV_DIR}" python=3.11 pythonocc-core pip fzf fd-find
fi

CONFIG_ARGS=()
while IFS= read -r line; do
  if [[ -n "${line}" ]]; then
    CONFIG_ARGS+=("${line}")
  fi
done < <("${PYTHON_BIN}" "${ROOT_DIR}/src/dfm_config.py" --print-args)

"${PYTHON_BIN}" "${ROOT_DIR}/src/dfm_check.py" "${STEP_FILE}" "${CONFIG_ARGS[@]}" "$@"
