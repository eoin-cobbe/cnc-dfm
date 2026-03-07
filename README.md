# cnc-dfm

## What this project is
`cnc-dfm` is a command-line Design for Manufacturing checker for CNC parts. Give it a STEP file and it analyzes geometry against six core machining rules, then returns a readable pass/fail report with a short explanation for each rule.

CLI command docs are in `/Users/eoincobbe/dev/cnc-dfm/docs/CLI_API.md` (regenerate with `make docs-cli`).
Onshape remediation plan is recorded in `/Users/eoincobbe/dev/cnc-dfm/docs/onshape_parametric_remediation_plan.md`.
FeatureScript helper setup is documented in `/Users/eoincobbe/dev/cnc-dfm/docs/ONSHAPE_FEATURESCRIPT_SETUP.md`.

## Install (one time)
```bash
git clone https://github.com/eoin-cobbe/cnc-dfm.git
cd cnc-dfm
./scripts/install.sh
run config
```

`run config` starts an interactive setup wizard and saves your Rule 1 to Rule 6 thresholds plus material selection permanently.  
Run it again anytime to overwrite and update the saved values.

`run config` also offers to save your Onshape API credentials. Those credentials are stored outside the git repo in your user config directory, not in this project folder, so they are not part of normal commits.

## Onshape Setup
1. Run:
```bash
run config
```
2. When prompted for Onshape auth, enter:
   - access key
   - secret key
   - base URL, usually `https://cad.onshape.com`
   - auth mode, usually `hmac`
3. The auth file is stored outside the repo at:
   - macOS/Linux default: `~/.config/cnc-dfm/onshape_auth.json`
   - override: `ONSHAPE_AUTH_CONFIG_PATH=/safe/path/onshape_auth.json`

Environment variables still work and override the saved auth file:
```bash
export ONSHAPE_ACCESS_KEY="your_access_key"
export ONSHAPE_SECRET_KEY="your_secret_key"
export ONSHAPE_BASE_URL="https://cad.onshape.com"
export ONSHAPE_AUTH_MODE="hmac"
```

Use `run show-config` to verify that auth is configured. The output redacts the key and never prints the secret.

## Onshape Use
Analyze an Onshape Part Studio:
```bash
run onshape analyze "https://cad.onshape.com/documents/<document_id>/w/<workspace_id>/e/<element_id>"
```

List proposals from a saved analysis session:
```bash
run onshape propose --session <session_id>
```

Apply one proposal:
```bash
run onshape apply --session <session_id> --proposal <proposal_id>
```

Phase 1 supports proposals against existing `Fillet`, `Extrude`, and `Hole` features only.
Paste a Part Studio URL, not an Assembly URL. If you open an assembly tab, this tool does not yet know which source part studio feature tree to edit, so it will stop and ask you to use the underlying Part Studio tab instead.
If the Part Studio contains multiple parts, phase 1 also stops instead of guessing which part to analyze. Today it only supports single-part Part Studios.

## Use it (2 steps, every time)

1. Open terminal and go to the folder that contains your STEP file.
```bash
cd /path/to/your/part/folder
```

2. Run the checker.
```bash
run
```

`run` opens an in-terminal STEP picker.  
If you already know the file path, you can run directly:
`run /path/to/part.step`.

If you did not add global `run`, use:
`/path/to/cnc-dfm/run /path/to/part.step`
