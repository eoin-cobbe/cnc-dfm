#!/usr/bin/env bash
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "${SOURCE}" ]; do
  DIR="$(cd -P "$(dirname "${SOURCE}")" && pwd)"
  SOURCE="$(readlink "${SOURCE}")"
  [[ "${SOURCE}" != /* ]] && SOURCE="${DIR}/${SOURCE}"
done
ROOT_DIR="$(cd -P "$(dirname "${SOURCE}")/.." && pwd)"
ENV_DIR="${ROOT_DIR}/.conda-env"
PYTHON_BIN="${ENV_DIR}/bin/python"
LINK_PATH="${HOME}/.local/bin/run"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

echo "[1/5] Checking package manager tooling"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install from https://brew.sh and re-run this script."
  exit 1
fi

if ! command -v mamba >/dev/null 2>&1; then
  echo "Installing Miniforge (mamba/conda)..."
  brew install --cask miniforge
fi

if ! command -v mamba >/dev/null 2>&1; then
  echo "mamba still not found after Miniforge install. Open a new shell and re-run."
  exit 1
fi

echo "[2/5] Creating project environment"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  mamba create -y -p "${ENV_DIR}" python=3.11 pythonocc-core pip fzf fd-find
fi

echo "[3/5] Verifying pythonOCC and picker tools"
need_fix=0
if ! "${PYTHON_BIN}" -c "import OCC" >/dev/null 2>&1; then
  need_fix=1
fi
if [[ ! -x "${ENV_DIR}/bin/fzf" ]]; then
  need_fix=1
fi
if [[ ! -x "${ENV_DIR}/bin/fd" && ! -x "${ENV_DIR}/bin/fdfind" ]]; then
  need_fix=1
fi

if (( need_fix == 1 )); then
  echo "Missing required packages in environment. Installing..."
  mamba install -y -p "${ENV_DIR}" pythonocc-core fzf fd-find
fi

"${PYTHON_BIN}" -c "import OCC; print('pythonocc ok')" >/dev/null

echo "[4/5] Installing global run command"
mkdir -p "${HOME}/.local/bin"
ln -sf "${ROOT_DIR}/run" "${LINK_PATH}"

touch "${HOME}/.zshrc" "${HOME}/.zprofile"
grep -qxF "${PATH_LINE}" "${HOME}/.zshrc" || echo "${PATH_LINE}" >> "${HOME}/.zshrc"
grep -qxF "${PATH_LINE}" "${HOME}/.zprofile" || echo "${PATH_LINE}" >> "${HOME}/.zprofile"

echo "[5/5] Final checks"
if [[ -n "${ZSH_VERSION:-}" ]]; then
  rehash
fi

if [[ ":${PATH}:" != *":${HOME}/.local/bin:"* ]]; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v run >/dev/null 2>&1; then
  echo "Install complete, but 'run' is not visible in this shell yet."
  echo "Run: source ~/.zshrc"
  exit 0
fi

echo "Install complete."
echo "Use:"
echo "  cd /path/to/parts"
echo "  run"
