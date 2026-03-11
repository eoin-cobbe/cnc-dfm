# macOS Swift App Plan

## Goal

Add a native macOS `.app` as an optional surface layer for `cnc-dfm` without turning the core product into a macOS-only codebase.

The rule engine, geometry analysis, configuration model, and reporting data should remain reusable from the existing Python core. The Swift app should own presentation, local file selection, app state, and macOS packaging only.

## What exists today

Current structure already points toward a clean split:

- [`src/dfm_check.py`](/Users/eoincobbe/dev/cnc-dfm/src/dfm_check.py): core analysis entrypoint plus report assembly
- [`src/dfm_terminal.py`](/Users/eoincobbe/dev/cnc-dfm/src/dfm_terminal.py): terminal-only output formatting
- [`src/dfm_config.py`](/Users/eoincobbe/dev/cnc-dfm/src/dfm_config.py): persisted config load/save and wizard
- [`run`](/Users/eoincobbe/dev/cnc-dfm/run) and [`scripts/run.sh`](/Users/eoincobbe/dev/cnc-dfm/scripts/run.sh): shell UX wrapper around the Python checker

This is a good starting point because the terminal renderer is already separate from the rule logic. The missing piece is a machine-readable application API between Python and any non-terminal client.

## Product direction

### Recommended architecture

Use a three-layer structure:

1. `core` in Python
   - Rule evaluation
   - STEP parsing
   - config persistence
   - process and cost calculations
2. `app api` in Python
   - stable JSON commands for config load/save and part analysis
   - no ANSI output
   - no interactive prompts
3. `macOS app` in SwiftUI
   - file picking and drag/drop
   - config forms
   - result presentation
   - recent files, local app state, export actions

### Why this is the right boundary

Calling the current CLI directly from Swift would work for a prototype, but it would be the wrong long-term contract because the CLI mixes:

- prompts
- shell assumptions
- ANSI formatting
- human-readable report layout

The app should depend on structured data, not parsed terminal output.

## Repo structure

Recommended target layout:

```text
src/
  dfm_core/                  # optional later refactor target
  dfm_check.py
  dfm_config.py
  dfm_terminal.py
  dfm_app_api.py            # new JSON interface for GUI and future integrations

apps/
  macos/
    CNCDFMApp/
      CNCDFMApp.xcodeproj
      CNCDFMApp/
        App/
        Features/
        Components/
        Services/
        Resources/
      Scripts/
        bundle-runtime.sh
        run-dev.sh

docs/
  MACOS_APP_PLAN.md
```

Notes:

- `apps/macos` stays optional and isolated.
- The Python source under `src/` remains the system of record.
- Cross-platform users can ignore the macOS app folder entirely.

## User flows to support first

Build phase 1 around the smallest complete workflow:

1. User opens the app.
2. App shows a single main workspace with an empty-state drop zone.
3. User drops a `.step` or `.stp` file, or chooses one from a native file picker.
4. App loads saved config from the same config source as the CLI.
5. User reviews or edits quantity and config values.
6. User runs analysis.
7. App shows:
   - part facts
   - cost summary
   - rule results
   - fail/pass state per rule
8. User can copy or export a report.

Do not build extra product surface before this works end to end.

### Phase 1 screens

- `Check`
  - empty state
  - selected file summary
  - run button
  - results view
- `Settings`
  - same config fields the CLI already supports
- `About` or `Diagnostics`
  - runtime status
  - Python backend path
  - config path

### Defer until later

- multi-document workflows
- side-by-side comparisons
- CAD preview
- cloud sync
- login/account features
- rewriting the rule engine in Swift

## Python changes required before Swift UI work

These are the first backend changes to make:

### 1. Add a stable JSON command surface

Create a new entrypoint such as:

```text
src/dfm_app_api.py
```

Commands:

- `config show --json`
- `config save --json-input <path-or-stdin>`
- `analyze --input /path/to/file.step --qty 10 --json`
- `materials --json`
- `health --json`

### 2. Separate report data from report rendering

`src/dfm_check.py` already computes structured values, but its `main()` still prints terminal output directly.

The next step is to expose a pure function that returns something like:

```json
{
  "file": "/path/to/part.step",
  "processData": {},
  "rules": [],
  "summary": {
    "passed": true,
    "failedRuleCount": 0
  }
}
```

The terminal renderer should become only one consumer of that structured result.

### 3. Keep config storage shared with the CLI

The app should read and write the same config model used by [`src/dfm_config.py`](/Users/eoincobbe/dev/cnc-dfm/src/dfm_config.py).

That avoids duplicated settings and keeps CLI and app behavior aligned.

## Swift app architecture

### UI framework

Use SwiftUI for the app shell and standard macOS system APIs for file access and process execution.

### Swift layers

- `Services`
  - `BackendProcessService`
  - `ConfigStore`
  - `RecentFilesStore`
- `Features/Check`
  - file selection
  - run state
  - results mapping
- `Features/Settings`
  - editable thresholds and material settings
- `Components`
  - cards
  - section headers
  - rule status rows
  - primary/secondary buttons

### Backend integration

Preferred integration:

- Swift launches bundled Python backend via `Process`
- Python returns JSON on stdout
- Swift decodes into `Codable` models

Avoid:

- scraping ANSI terminal output
- embedding rule logic in Swift
- calling the interactive `run` script from the app

## Packaging approach for a downloadable `.app`

### Requirement

Users should be able to download and run a macOS app bundle without manually recreating the CLI environment.

### Recommended packaging plan

Bundle a self-contained backend inside the app:

- `CNCDFM.app/Contents/Resources/backend/`
  - Python runtime or app-specific environment
  - Python source
  - required native dependencies

The Swift app launches the bundled backend directly.

### Why this preserves cross-platform support

- The repo remains Python-first and platform-agnostic in `src/`.
- The macOS app is an optional adapter in `apps/macos/`.
- Linux and Windows future surfaces can reuse the same JSON backend contract.

### Release model

Keep releases separate:

- CLI release flow remains unchanged
- macOS release produces `CNCDFM.app.zip` or `CNCDFM.dmg`

Do not make the repo root build depend on Xcode tooling.

## Styling direction

The app should stay visually close to the Codex desktop app style:

- restrained, utility-first layout
- layered neutral surfaces
- subtle borders and separators
- compact controls
- one primary accent color
- minimal illustration
- simple left-to-right information flow

### macOS-native styling decisions

- Background:
  - use dynamic system background colors and materials
  - follow light/dark appearance automatically
- Accent:
  - use macOS system blue as the primary accent via `NSColor.systemBlue`
  - keep blue reserved for primary actions, selected states, links, and active indicators
- Typography:
  - use SF Pro through system fonts
  - strong hierarchy, not oversized marketing text
- Iconography:
  - use SF Symbols only in phase 1
- Layout:
  - single main window
  - simple sidebar or narrow left rail
  - broad content pane with cards/sections

### Suggested first window layout

- Left rail:
  - `Check`
  - `Settings`
  - `Diagnostics`
- Main pane:
  - top toolbar with file actions
  - empty state or result content
  - cards for facts, costs, and rules

### Visual constraints

- no heavy gradients
- no decorative illustration system
- no crowded tables for the first pass
- no more than one primary button in view at a time

## Implementation phases

### Phase 0: backend contract

- add `dfm_app_api.py`
- return JSON for config, materials, health, and analysis
- refactor CLI to consume shared analysis functions
- keep terminal rendering in `dfm_terminal.py`

### Phase 1: macOS shell

- create SwiftUI app in `apps/macos`
- add native file picker and drag/drop
- add backend process bridge
- show analysis results
- add settings form backed by shared config

### Phase 2: packaging

- bundle backend into `.app`
- add local diagnostics page
- document build and release steps
- produce first downloadable artifact

### Phase 3: quality and polish

- recent files
- export report
- better empty/error states
- simple onboarding on first launch

## Immediate next build step

Do this next before any Swift UI implementation:

1. Extract a structured Python analysis result model.
2. Add the JSON app API entrypoint.
3. Keep the CLI using the same shared backend functions.

If that boundary is correct, the Swift app becomes straightforward. If that boundary is wrong, every UI pass will fight the terminal-oriented code.
