#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
APP_NAME="CNCDFMApp"
APP_DIR="${DIST_DIR}/${APP_NAME}-bundled.app"
VERSION="${VERSION:-0.1.0}"
BUILD_NUMBER="${BUILD_NUMBER:-1}"
ARTIFACT_NAME="${APP_NAME}-${VERSION}-macos.zip"
ARTIFACT_PATH="${DIST_DIR}/${ARTIFACT_NAME}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_SIGN="${SKIP_SIGN:-0}"

if [[ "${SKIP_BUILD}" == "1" ]]; then
  echo "[1/4] Reusing existing bundled app"
  if [[ ! -d "${APP_DIR}" ]]; then
    echo "Bundled app not found at ${APP_DIR}" >&2
    exit 1
  fi
else
  echo "[1/4] Building bundled app"
  VERSION="${VERSION}" BUILD_NUMBER="${BUILD_NUMBER}" "${ROOT_DIR}/Scripts/build-bundled-app.sh"
fi

if [[ "${SKIP_SIGN}" == "1" ]]; then
  echo "[2/4] Reusing existing app signature"
elif [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  echo "[2/4] Applying Developer ID signature"
  codesign --force --deep --options runtime --sign "${CODESIGN_IDENTITY}" "${APP_DIR}"
else
  echo "[2/4] Skipping Developer ID signature (set CODESIGN_IDENTITY to enable)"
fi

echo "[3/4] Creating release zip"
rm -f "${ARTIFACT_PATH}"
ditto -c -k --sequesterRsrc --keepParent "${APP_DIR}" "${ARTIFACT_PATH}"

echo "[4/4] Release artifact ready"
echo "${ARTIFACT_PATH}"

if [[ "${SKIP_SIGN}" != "1" && -z "${CODESIGN_IDENTITY:-}" ]]; then
  cat <<'EOF'
Note: this zip contains an ad-hoc-signed app. That is fine for internal testing and GitHub uploads,
but public macOS releases should use Developer ID signing and notarization.
EOF
fi
