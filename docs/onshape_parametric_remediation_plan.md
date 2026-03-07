# Onshape Parametric Remediation Plan

## Overview
Build a phase-1 CLI workflow that connects to an Onshape Part Studio, exports a STEP for the existing OCC rule engine, maps failing geometry back to supported Onshape features, proposes parameter edits, asks for confirmation, applies one edit at a time, then re-exports and re-runs DFM.

Phase 1 supports modifying existing `Fillet`, `Extrude`, and `Hole` features only. It does not create new features, and it does not attempt Rule 0 remediation.

## Supported Phase-1 Edits
- `Rule 1`: increase an existing fillet radius.
- `Rule 2`: reduce a blind extrude depth.
- `Rule 4`: reduce hole depth or increase hole diameter.
- `Rule 6`: reuse the Rule 1 or Rule 2 edit strategy based on the mapped governing feature.
- `Rule 3`: diagnose only unless a future revision adds a safe single-parameter mapping path.

## Architecture
- `run onshape analyze --did <id> --wid <id> --eid <id> [--configuration <expr>]`
  Exports STEP, runs OCC DFM, maps offenders, stores an analysis session, and prints ranked proposals.
- `run onshape propose --session <id>`
  Lists the stored proposals for a prior analysis session.
- `run onshape apply --session <id> --proposal <id>`
  Applies one confirmed feature-parameter edit, re-exports STEP, and reruns DFM.

Code layout:
- `src/onshape/auth.py`: Onshape auth and request headers.
- `src/onshape/client.py`: REST access for features, FeatureScript, export, and update flows.
- `src/onshape/export.py`: STEP export/download lifecycle.
- `src/onshape/fs_eval.py`: reusable `evalFeatureScript` wrappers.
- `src/onshape/feature_parser.py`: normalize supported feature parameters.
- `src/onshape/mapper.py`: conservative offender-to-feature matching.
- `src/onshape/remediation.py`: proposal generation.
- `src/onshape/session.py`: persisted session state under `cache/onshape_sessions/`.
- `src/onshape_cli.py`: CLI entrypoint.

## Mapping Strategy
1. Fetch Part Studio features from Onshape and parse supported feature families.
2. Export a STEP of the current workspace/configuration.
3. Run OCC DFM and emit structured offenders with geometry anchors and target dimensions.
4. Evaluate FeatureScript traces for supported features using `qCreatedBy(...)` and transient query strings.
5. Score candidates conservatively by feature-type compatibility, numeric similarity, and available FeatureScript evidence.
6. Reject weak or ambiguous matches instead of forcing an edit.
7. Generate one or more proposals per offender when the parameter path is explicit and editable.

## Failure Handling
- If Onshape credentials are missing, the CLI exits with an auth error.
- If STEP export or translation fails, the analysis aborts with the upstream API response.
- If FeatureScript tracing fails, analysis continues with lower-confidence matching.
- If multiple candidates are too close, no proposal is emitted for that offender.
- If a proposal targets an expression-driven parameter, it is surfaced but not auto-applied.
- If the workspace microversion changed before apply, the session audit log records the drift and the CLI refetches feature state before updating.
- If the feature update fails regeneration or parameter lookup, the apply step stops and records the failure.

## Acceptance Tests
- Fillet radius offender maps to one fillet parameter and produces a radius-increase proposal.
- Blind pocket offender maps to one extrude depth parameter and produces a depth-reduction proposal.
- Hole ratio offender can produce a depth-reduction proposal and a diameter-increase proposal.
- Thin-wall offenders are preserved as diagnose-only outputs.
- Session save/load preserves offenders, candidate evidence, proposals, and audit log.
- Ambiguous candidate matches are rejected instead of auto-selected.

## Revision History
- 2026-03-07: Initial implementation record for the Onshape CLI prototype, structured offender output, proposal persistence, and single-edit apply loop.
