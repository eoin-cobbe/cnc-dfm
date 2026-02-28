#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ROOT_DIR}/.conda-env"
PYTHON_BIN="${ENV_DIR}/bin/python"
OUT_FILE="${ROOT_DIR}/docs/CLI_API.md"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing Python runtime at ${PYTHON_BIN}. Run ./scripts/install.sh first." >&2
  exit 1
fi

CHECK_HELP="$(${PYTHON_BIN} "${ROOT_DIR}/src/dfm_check.py" --help)"
CONFIG_HELP="$(${PYTHON_BIN} "${ROOT_DIR}/src/dfm_config.py" --help)"

cat > "${OUT_FILE}" <<EOF
# CLI API Docs

This file is generated from the current CLI entrypoints.
Regenerate with:

\`\`\`bash
make docs-cli
\`\`\`

## Main Commands

- \`run\`: Launch the CNC-DFM checker (opens STEP picker if no file passed)
- \`run /path/to/part.step\`: Run checker on a specific file
- \`run config\`: Interactive setup wizard for R1-R6 thresholds
- \`run show-config\`: Show saved threshold config currently used by \`run\`

## Checker CLI (src/dfm_check.py --help)

\`\`\`text
${CHECK_HELP}
\`\`\`

## Config CLI (src/dfm_config.py --help)

\`\`\`text
${CONFIG_HELP}
\`\`\`

## Persistent Config

- Default path: \`/Users/eoincobbe/dev/cnc-dfm/cache/dfm_config.json\`
- Override path with env var: \`CNC_DFM_CONFIG_PATH\`
EOF

echo "Wrote ${OUT_FILE}"
