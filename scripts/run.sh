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

has_qty_arg=0
for arg in "$@"; do
  if [[ "${arg}" == "--qty" || "${arg}" == --qty=* ]]; then
    has_qty_arg=1
    break
  fi
done

declare -a QTY_ARG=()
if [[ ${has_qty_arg} -eq 0 && -t 0 ]]; then
  while true; do
    read -r -p "qty: " qty_input
    if [[ "${qty_input}" =~ ^[1-9][0-9]*$ ]]; then
      QTY_ARG=(--qty "${qty_input}")
      break
    fi
    echo "Please enter a whole number >= 1."
  done
fi

CMD=("${PYTHON_BIN}" "${ROOT_DIR}/src/dfm_check.py" "${STEP_FILE}" "${CONFIG_ARGS[@]}")
if [[ ${#QTY_ARG[@]} -gt 0 ]]; then
  CMD+=("${QTY_ARG[@]}")
fi
CMD+=("$@")
"${CMD[@]}"
