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
ONSHAPE_HELP="$(${PYTHON_BIN} "${ROOT_DIR}/src/onshape_cli.py" --help)"

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
- \`run config\`: Interactive setup wizard for R1-R6 thresholds and optional Onshape auth setup
- \`run show-config\`: Show saved threshold config and redacted Onshape auth summary
- \`run onshape analyze ...\`: Export an Onshape Part Studio, run DFM, and persist proposals
- \`run onshape propose --session <id>\`: Show stored proposals for a prior Onshape analysis
- \`run onshape apply --session <id> --proposal <id>\`: Apply one stored proposal and rerun DFM

## Onshape Auth Setup

- Recommended: run \`run config\` and save the keys when prompted
- Default auth file path: \`~/.config/cnc-dfm/onshape_auth.json\`
- Optional override path: \`ONSHAPE_AUTH_CONFIG_PATH=/safe/path/onshape_auth.json\`
- Environment variables still work and override the saved auth file:
  - \`ONSHAPE_ACCESS_KEY\`
  - \`ONSHAPE_SECRET_KEY\`
  - \`ONSHAPE_BASE_URL\`
  - \`ONSHAPE_AUTH_MODE\`
- The auth file is intentionally stored outside the repository so it is not part of normal git commits

## Onshape Quick Start

\`\`\`bash
run config
run onshape analyze "https://cad.onshape.com/documents/<document_id>/w/<workspace_id>/e/<element_id>"
run onshape propose --session <session_id>
run onshape apply --session <session_id> --proposal <proposal_id>
\`\`\`

Notes:
- Paste a workspace Part Studio URL
- Assembly URLs are rejected
- Multi-part Part Studios are rejected in phase 1 rather than guessed

## Checker CLI (src/dfm_check.py --help)

\`\`\`text
${CHECK_HELP}
\`\`\`

## Config CLI (src/dfm_config.py --help)

\`\`\`text
${CONFIG_HELP}
\`\`\`

## Onshape CLI (src/onshape_cli.py --help)

\`\`\`text
${ONSHAPE_HELP}
\`\`\`

## Persistent Config

- Default path: \`/Users/eoincobbe/dev/cnc-dfm/cache/dfm_config.json\`
- Override path with env var: \`CNC_DFM_CONFIG_PATH\`
- Onshape auth path: \`~/.config/cnc-dfm/onshape_auth.json\`
- Onshape auth override path: \`ONSHAPE_AUTH_CONFIG_PATH\`
EOF

echo "Wrote ${OUT_FILE}"
