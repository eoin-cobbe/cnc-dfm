# CNCDFMApp

Native macOS SwiftUI shell for `cnc-dfm`.

## Current scope

This package is the first app scaffold:

- SwiftUI macOS shell
- backend process bridge to `src/dfm_app_api.py`
- `Check`, `Settings`, and `Diagnostics` screens
- local development workflow against the existing repo checkout

This source lives in the open-source repo on purpose:

- Python remains the shared cross-platform backend
- the macOS app is just another client of that backend
- generated `.app` bundles and release archives should not be committed

There are two different ways to run it:

1. development run from source
2. local native `.app` bundle built from this repo
3. self-contained `.app` bundle for packaging tests

Portable downloadable distribution for other users is a separate packaging step because the backend runtime still has to be bundled in a relocatable way.

## Run

From this directory:

```bash
swift run
```

The app will try to find the repo root by walking up from the source tree until it finds `src/dfm_app_api.py`.

Optional overrides:

- `CNC_DFM_REPO_ROOT=/absolute/path/to/cnc-dfm`
- `CNC_DFM_PYTHON=/absolute/path/to/python`

If `CNC_DFM_PYTHON` is not set, the app prefers:

1. `<repo>/.conda-env/bin/python`
2. `/usr/bin/env python3`

## Build

```bash
swift build
```

## Build A Local Native App

From this directory:

```bash
./Scripts/build-local-app.sh
```

That produces:

```text
dist/CNCDFMApp.app
```

This local `.app` is meant for your machine and points back to this repo checkout through a small resource marker file. It is native and double-clickable, but it is not yet a portable app for sharing with other users.

To open it:

```bash
./Scripts/open-local-app.sh
```

## Build A Self-Contained Test App

```bash
./Scripts/build-bundled-app.sh
```

That produces:

```text
dist/CNCDFMApp-bundled.app
```

This bundle includes:

- the app binary
- the Python backend source
- the Python runtime used by the backend

To smoke-test the embedded backend directly:

```bash
./Scripts/test-bundled-backend.sh
```

To open the bundled app:

```bash
./Scripts/open-bundled-app.sh
```

To prove the embedded backend still works after copying the app outside the repo:

```bash
./Scripts/test-bundled-relocated.sh
```

## What Counts As A Downloadable Release

For other people to download and click without needing your repo checkout, the app bundle needs:

- the backend source inside the app or another controlled runtime location
- a bundled Python runtime that can import `OCC`
- app packaging output such as `.zip` or `.dmg`
- ideally code signing and notarization for smooth macOS launch behavior

The self-contained test app gets you most of the way there technically. A real public download still needs release packaging, testing on a clean machine, and signing/notarization.

## Build A GitHub Release Artifact

Create a versioned zip from the bundled app:

```bash
VERSION=0.1.0 BUILD_NUMBER=1 ./Scripts/package-release-zip.sh
```

That produces:

```text
dist/CNCDFMApp-0.1.0-macos.zip
```

This script:

- rebuilds `dist/CNCDFMApp-bundled.app`
- stamps the app bundle version in `Info.plist`
- optionally applies Developer ID signing if `CODESIGN_IDENTITY` is set
- zips the `.app` with `ditto` so Finder metadata is preserved

Example with signing:

```bash
VERSION=0.1.0 BUILD_NUMBER=1 \
CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
./Scripts/package-release-zip.sh
```

Upload the generated zip to GitHub Releases as the macOS desktop artifact.

For a smooth public install experience, notarize the signed zip before uploading:

```bash
xcrun notarytool submit dist/CNCDFMApp-0.1.0-macos.zip \
  --apple-id "you@example.com" \
  --team-id "TEAMID" \
  --password "app-specific-password" \
  --wait

xcrun stapler staple dist/CNCDFMApp-bundled.app
```

After stapling, recreate the zip without rebuilding or re-signing so the stapled app is what you upload:

```bash
VERSION=0.1.0 SKIP_BUILD=1 SKIP_SIGN=1 ./Scripts/package-release-zip.sh
```
