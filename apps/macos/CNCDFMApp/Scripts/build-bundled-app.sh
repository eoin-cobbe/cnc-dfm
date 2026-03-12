#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/../../.." && pwd)"
APP_NAME="CNCDFMApp"
DIST_DIR="${ROOT_DIR}/dist"
APP_DIR="${DIST_DIR}/${APP_NAME}-bundled.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
BACKEND_DIR="${RESOURCES_DIR}/backend"
VERSION="${VERSION:-0.1.0}"
BUILD_NUMBER="${BUILD_NUMBER:-1}"
BUNDLE_ID="${BUNDLE_ID:-dev.eoincobbe.cncdfmapp.bundled}"

echo "[1/6] Building Swift app"
swift build -c release

BIN_DIR="$(swift build -c release --show-bin-path)"
APP_BIN="${BIN_DIR}/${APP_NAME}"

if [[ ! -x "${APP_BIN}" ]]; then
  echo "Missing app binary at ${APP_BIN}" >&2
  exit 1
fi

echo "[2/6] Creating app bundle"
rm -rf "${APP_DIR}"
mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}" "${BACKEND_DIR}"

cp "${APP_BIN}" "${MACOS_DIR}/${APP_NAME}"
chmod +x "${MACOS_DIR}/${APP_NAME}"

cat > "${CONTENTS_DIR}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "https://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleVersion</key>
  <string>${BUILD_NUMBER}</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

echo "[3/6] Copying backend source"
rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  "${REPO_ROOT}/src" "${BACKEND_DIR}/"

echo "[4/6] Copying Python runtime"
rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  "${REPO_ROOT}/.conda-env" "${BACKEND_DIR}/"

mkdir -p "${BACKEND_DIR}/cache/previews"

echo "[5/6] Writing bundle test helper"
cat > "${RESOURCES_DIR}/README-self-contained.txt" <<EOF
This app bundle contains its own backend and Python runtime.
It should not need the original repo checkout to run.
EOF

echo "[6/6] Applying local ad-hoc signature"
codesign --force --deep --sign - "${APP_DIR}" >/dev/null 2>&1 || true

echo "Bundled app ready:"
echo "${APP_DIR}"
