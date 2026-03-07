# CNCDFMApp

Native macOS SwiftUI shell for `cnc-dfm`.

## Current scope

This package is the first app scaffold:

- SwiftUI macOS shell
- backend process bridge to `src/dfm_app_api.py`
- `Check`, `Settings`, and `Diagnostics` screens
- local development workflow against the existing repo checkout

It is not yet a packaged `.app` release artifact. Packaging comes after the shell and backend contract are stable.

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
