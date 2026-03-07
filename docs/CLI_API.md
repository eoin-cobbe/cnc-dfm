# CLI API Docs

This file is generated from the current CLI entrypoints.
Regenerate with:

```bash
make docs-cli
```

## Main Commands

- `run`: Launch the CNC-DFM checker (opens STEP picker if no file passed)
- `run /path/to/part.step`: Run checker on a specific file
- `run config`: Interactive setup wizard for R1-R6 thresholds and optional Onshape auth setup
- `run show-config`: Show saved threshold config and redacted Onshape auth summary
- `run onshape analyze ...`: Export an Onshape Part Studio, run DFM, and persist proposals
- `run onshape propose --session <id>`: Show stored proposals for a prior Onshape analysis
- `run onshape apply --session <id> --proposal <id>`: Apply one stored proposal and rerun DFM

## Onshape Auth Setup

- Recommended: run `run config` and save the keys when prompted
- Default auth file path: `~/.config/cnc-dfm/onshape_auth.json`
- Optional override path: `ONSHAPE_AUTH_CONFIG_PATH=/safe/path/onshape_auth.json`
- Environment variables still work and override the saved auth file:
  - `ONSHAPE_ACCESS_KEY`
  - `ONSHAPE_SECRET_KEY`
  - `ONSHAPE_BASE_URL`
  - `ONSHAPE_AUTH_MODE`
- The auth file is intentionally stored outside the repository so it is not part of normal git commits

## Onshape Quick Start

```bash
run config
run onshape analyze "https://cad.onshape.com/documents/<document_id>/w/<workspace_id>/e/<element_id>"
run onshape propose --session <session_id>
run onshape apply --session <session_id> --proposal <proposal_id>
```

Notes:
- Paste a workspace Part Studio URL
- Assembly URLs are rejected
- Multi-part Part Studios are rejected in phase 1 rather than guessed

## Checker CLI (src/dfm_check.py --help)

```text
usage: dfm_check.py [-h] [--qty QTY] [--min-radius MIN_RADIUS]
                    [--max-pocket-ratio MAX_POCKET_RATIO]
                    [--min-wall MIN_WALL] [--max-hole-ratio MAX_HOLE_RATIO]
                    [--max-setups MAX_SETUPS]
                    [--max-tool-depth-ratio MAX_TOOL_DEPTH_RATIO]
                    [--material {6061_aluminium,304_stainless_steel,1080_steel,grade_5_titanium}]
                    [--baseline-6061-mrr BASELINE_6061_MRR]
                    [--machine-hourly-rate-3-axis-eur MACHINE_HOURLY_RATE_3_AXIS_EUR]
                    [--machine-hourly-rate-5-axis-eur MACHINE_HOURLY_RATE_5_AXIS_EUR]
                    [--material-billet-cost-eur-per-kg MATERIAL_BILLET_COST_EUR_PER_KG]
                    [--surface-penalty-slope SURFACE_PENALTY_SLOPE]
                    [--surface-penalty-max-multiplier SURFACE_PENALTY_MAX_MULTIPLIER]
                    [--complexity-penalty-per-face COMPLEXITY_PENALTY_PER_FACE]
                    [--complexity-penalty-max-multiplier COMPLEXITY_PENALTY_MAX_MULTIPLIER]
                    [--complexity-baseline-faces COMPLEXITY_BASELINE_FACES]
                    [--hole-count-penalty-per-feature HOLE_COUNT_PENALTY_PER_FEATURE]
                    [--hole-count-penalty-max-multiplier HOLE_COUNT_PENALTY_MAX_MULTIPLIER]
                    [--radius-count-penalty-per-feature RADIUS_COUNT_PENALTY_PER_FEATURE]
                    [--radius-count-penalty-max-multiplier RADIUS_COUNT_PENALTY_MAX_MULTIPLIER]
                    [--qty-learning-rate QTY_LEARNING_RATE]
                    [--qty-factor-floor QTY_FACTOR_FLOOR]
                    step_file

CLI DFM checker for STEP files (pythonOCC).

positional arguments:
  step_file             Path to input STEP file

options:
  -h, --help            show this help message and exit
  --qty QTY             Batch quantity for learning-curve scaling
  --min-radius MIN_RADIUS
                        Rule 1 recommended min internal radius (mm); pass
                        floor is fixed at 0.8 mm
  --max-pocket-ratio MAX_POCKET_RATIO
                        Rule 2 max pocket depth ratio
  --min-wall MIN_WALL   Rule 3 min wall thickness (mm)
  --max-hole-ratio MAX_HOLE_RATIO
                        Rule 4 max hole depth/diameter ratio
  --max-setups MAX_SETUPS
                        Rule 5 max setup faces/axes
  --max-tool-depth-ratio MAX_TOOL_DEPTH_RATIO
                        Rule 6 max pocket depth/tool diameter ratio
  --material {6061_aluminium,304_stainless_steel,1080_steel,grade_5_titanium}
                        Part material key
  --baseline-6061-mrr BASELINE_6061_MRR
                        Baseline 6061 roughing MRR (mm^3/min) used to estimate
                        other materials
  --machine-hourly-rate-3-axis-eur MACHINE_HOURLY_RATE_3_AXIS_EUR
                        3-axis machine hourly rate in EUR/hr for roughing cost
                        estimate
  --machine-hourly-rate-5-axis-eur MACHINE_HOURLY_RATE_5_AXIS_EUR
                        5-axis machine hourly rate in EUR/hr for roughing cost
                        estimate
  --material-billet-cost-eur-per-kg MATERIAL_BILLET_COST_EUR_PER_KG
                        Billet cost in EUR/kg for selected material (defaults
                        to material baseline)
  --surface-penalty-slope SURFACE_PENALTY_SLOPE
                        Surface-area slope for surface-area multiplier (time
                        penalty)
  --surface-penalty-max-multiplier SURFACE_PENALTY_MAX_MULTIPLIER
                        Maximum surface-area multiplier
  --complexity-penalty-per-face COMPLEXITY_PENALTY_PER_FACE
                        Complexity penalty slope per face above baseline
  --complexity-penalty-max-multiplier COMPLEXITY_PENALTY_MAX_MULTIPLIER
                        Maximum complexity multiplier
  --complexity-baseline-faces COMPLEXITY_BASELINE_FACES
                        Face-count baseline before complexity penalty starts
  --hole-count-penalty-per-feature HOLE_COUNT_PENALTY_PER_FEATURE
                        Penalty per detected hole feature (adds to multiplier)
  --hole-count-penalty-max-multiplier HOLE_COUNT_PENALTY_MAX_MULTIPLIER
                        Maximum hole-count multiplier
  --radius-count-penalty-per-feature RADIUS_COUNT_PENALTY_PER_FEATURE
                        Penalty per detected internal radius feature (adds to
                        multiplier)
  --radius-count-penalty-max-multiplier RADIUS_COUNT_PENALTY_MAX_MULTIPLIER
                        Maximum radius-count multiplier
  --qty-learning-rate QTY_LEARNING_RATE
                        Learning rate for quantity scaling (e.g., 0.90 means
                        10% reduction per quantity doubling)
  --qty-factor-floor QTY_FACTOR_FLOOR
                        Minimum quantity multiplier floor
```

## Config CLI (src/dfm_config.py --help)

```text
usage: dfm_config.py [-h] [--wizard] [--print-args] [--show]

CNC-DFM config manager

options:
  -h, --help    show this help message and exit
  --wizard      Run interactive setup
  --print-args  Print saved config as CLI args
  --show        Show current saved config
```

## Onshape CLI (src/onshape_cli.py --help)

```text
usage: onshape_cli.py [-h] {analyze,propose,apply} ...

Onshape CLI prototype for CNC-DFM remediation.

positional arguments:
  {analyze,propose,apply}
    analyze             Export an Onshape Part Studio, run DFM, and store
                        proposals.
    propose             List stored proposals for a prior Onshape analysis
                        session.
    apply               Apply one stored remediation proposal and rerun DFM.

options:
  -h, --help            show this help message and exit
```

## Persistent Config

- Default path: `/Users/eoincobbe/dev/cnc-dfm/cache/dfm_config.json`
- Override path with env var: `CNC_DFM_CONFIG_PATH`
- Onshape auth path: `~/.config/cnc-dfm/onshape_auth.json`
- Onshape auth override path: `ONSHAPE_AUTH_CONFIG_PATH`
