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

## What Counts As A Downloadable Release

For other people to download and click without needing your repo checkout, the app bundle needs:

- the backend source inside the app or another controlled runtime location
- a bundled Python runtime that can import `OCC`
- app packaging output such as `.zip` or `.dmg`
- ideally code signing and notarization for smooth macOS launch behavior

That is the next packaging phase, not the current local-development phase.
