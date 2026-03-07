#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ROOT_DIR}/.conda-env"
PYTHON_BIN="${ENV_DIR}/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  mamba create -y -p "${ENV_DIR}" python=3.11 pythonocc-core pip fzf fd-find
fi

exec "${PYTHON_BIN}" "${ROOT_DIR}/src/onshape_cli.py" "$@"
