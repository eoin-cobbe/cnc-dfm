#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import OrderedDict
import re
from typing import Dict, Iterable, List
from urllib.parse import parse_qs, urlparse

from dfm_check import combined_rule_multiplier, compute_part_process_data, run_all_rules
from dfm_config import load_config
from dfm_geometry import read_step
from dfm_materials import get_material, material_keys
from dfm_models import (
    AnalysisSession,
    Config,
    FeatureCandidate,
    OffenderRecord,
    OnshapeTarget,
    RemediationProposal,
)
from dfm_terminal import print_boot, print_part_process_data, print_report
from onshape.client import OnshapeClient, OnshapeError
from onshape.export import export_partstudio_step
from onshape.feature_parser import parse_supported_features
from onshape.fs_eval import collect_feature_fingerprints
from onshape.mapper import match_offenders_to_candidates
from onshape.remediation import build_proposals
from onshape.session import append_audit, load_session, new_session_id, save_session

ONSHAPE_URL_RE = re.compile(
    r"^/documents/(?P<did>[^/]+)/(?P<wvm>[wvm])/(?P<wvmid>[^/]+)/e/(?P<eid>[^/?#]+)$"
)


def _saved_value(overrides: argparse.Namespace, key: str, fallback):
    value = getattr(overrides, key)
    return fallback if value is None else value


def build_cfg(args: argparse.Namespace) -> Config:
    saved = load_config()
    material_key = _saved_value(args, "material", saved["material"])
    selected_material = get_material(material_key)
    billet_cost = _saved_value(
        args,
        "material_billet_cost_eur_per_kg",
        saved.get("material_billet_cost_eur_per_kg", selected_material.baseline_billet_cost_eur_per_kg),
    )
    return Config(
        min_internal_corner_radius_mm=_saved_value(args, "min_radius", saved["min_radius"]),
        max_pocket_depth_ratio=_saved_value(args, "max_pocket_ratio", saved["max_pocket_ratio"]),
        max_tool_depth_to_diameter_ratio=_saved_value(args, "max_tool_depth_ratio", saved["max_tool_depth_ratio"]),
        min_wall_thickness_mm=_saved_value(args, "min_wall", saved["min_wall"]),
        max_hole_depth_to_diameter=_saved_value(args, "max_hole_ratio", saved["max_hole_ratio"]),
        max_setups=_saved_value(args, "max_setups", saved["max_setups"]),
        material_key=material_key,
        baseline_6061_mrr_mm3_per_min=_saved_value(args, "baseline_6061_mrr", saved["baseline_6061_mrr"]),
        machine_hourly_rate_3_axis_eur=_saved_value(
            args, "machine_hourly_rate_3_axis_eur", saved["machine_hourly_rate_3_axis_eur"]
        ),
        machine_hourly_rate_5_axis_eur=_saved_value(
            args, "machine_hourly_rate_5_axis_eur", saved["machine_hourly_rate_5_axis_eur"]
        ),
        material_billet_cost_eur_per_kg=billet_cost,
        surface_penalty_slope=_saved_value(args, "surface_penalty_slope", saved["surface_penalty_slope"]),
        surface_penalty_max_multiplier=_saved_value(
            args, "surface_penalty_max_multiplier", saved["surface_penalty_max_multiplier"]
        ),
        complexity_penalty_per_face=_saved_value(args, "complexity_penalty_per_face", saved["complexity_penalty_per_face"]),
        complexity_penalty_max_multiplier=_saved_value(
            args, "complexity_penalty_max_multiplier", saved["complexity_penalty_max_multiplier"]
        ),
        complexity_baseline_faces=_saved_value(args, "complexity_baseline_faces", saved["complexity_baseline_faces"]),
        hole_count_penalty_per_feature=_saved_value(
            args, "hole_count_penalty_per_feature", saved["hole_count_penalty_per_feature"]
        ),
        hole_count_penalty_max_multiplier=_saved_value(
            args, "hole_count_penalty_max_multiplier", saved["hole_count_penalty_max_multiplier"]
        ),
        radius_count_penalty_per_feature=_saved_value(
            args, "radius_count_penalty_per_feature", saved["radius_count_penalty_per_feature"]
        ),
        radius_count_penalty_max_multiplier=_saved_value(
            args, "radius_count_penalty_max_multiplier", saved["radius_count_penalty_max_multiplier"]
        ),
        qty_learning_rate=_saved_value(args, "qty_learning_rate", saved["qty_learning_rate"]),
        qty_factor_floor=_saved_value(args, "qty_factor_floor", saved["qty_factor_floor"]),
    )


def _rule_id(name: str) -> str:
    if "Rule 0" in name:
        return "R0"
    if "Rule 1" in name:
        return "R1"
    if "Rule 2" in name:
        return "R2"
    if "Rule 3" in name:
        return "R3"
    if "Rule 4" in name:
        return "R4"
    if "Rule 5" in name:
        return "R5"
    if "Rule 6" in name:
        return "R6"
    return name


def _flatten_offenders(results) -> List[OffenderRecord]:
    offenders: List[OffenderRecord] = []
    for result in results:
        offenders.extend(result.offenders)
    return offenders


def _flatten_candidates(match_map: Dict[int, List[FeatureCandidate]]) -> List[FeatureCandidate]:
    rows = OrderedDict()
    for idx, candidates in match_map.items():
        for candidate in candidates[:3]:
            key = (idx, candidate.feature_id, candidate.parameter_id)
            rows[key] = candidate
    return list(rows.values())


def _print_proposals(proposals: Iterable[RemediationProposal]) -> None:
    proposals = list(proposals)
    if not proposals:
        print("No safe remediation proposals were generated.")
        return
    print("PROPOSALS")
    for proposal in proposals:
        print(
            f"  {proposal.proposal_id}  {proposal.rule_id}  {proposal.feature_type}:{proposal.feature_id}  "
            f"{proposal.before} -> {proposal.after}  confidence={proposal.confidence:.2f}"
        )
        print(f"       {proposal.rationale}")


def _features_payload_microversion(payload: Dict[str, object]) -> str:
    for key in ("sourceMicroversion", "serializationVersion", "microversionSkew"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return ""


def _target_from_args(args: argparse.Namespace) -> OnshapeTarget:
    if getattr(args, "url", None):
        target = _parse_onshape_url(args.url)
        if args.configuration:
            target.configuration = args.configuration
        return target
    if getattr(args, "target", None):
        target = _parse_onshape_url(args.target)
        if args.configuration:
            target.configuration = args.configuration
        return target
    if args.did and args.wid and args.eid:
        return OnshapeTarget(did=args.did, wid=args.wid, eid=args.eid, configuration=args.configuration)
    raise OnshapeError("Provide either a full Onshape URL or all of --did, --wid, and --eid.")


def _parse_onshape_url(raw_url: str) -> OnshapeTarget:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OnshapeError("Expected a full Onshape URL like https://cad.onshape.com/documents/.../w/.../e/...")
    match = ONSHAPE_URL_RE.match(parsed.path.rstrip("/"))
    if not match:
        raise OnshapeError("Unsupported Onshape URL format. Paste a document tab URL ending in /w/<workspace>/e/<element>.")
    if match.group("wvm") != "w":
        raise OnshapeError("Only workspace URLs are supported for edits. Open the workspace tab and copy its /w/.../e/... URL.")
    query = parse_qs(parsed.query)
    configuration = query.get("configuration", [None])[0]
    return OnshapeTarget(
        did=match.group("did"),
        wid=match.group("wvmid"),
        eid=match.group("eid"),
        configuration=configuration,
    )


def _resolve_element(client: OnshapeClient, target: OnshapeTarget) -> Dict[str, str]:
    payload = client.get_elements(target)
    if not isinstance(payload, list):
        raise OnshapeError("Unexpected Onshape element listing response.")
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("id", "")).strip() != target.eid:
            continue
        return {
            "id": str(row.get("id", "")),
            "name": str(row.get("name", "")),
            "type": str(row.get("elementType", "")),
        }
    raise OnshapeError(f"Element {target.eid} was not found in document {target.did}.")


def _validate_target_is_partstudio(client: OnshapeClient, target: OnshapeTarget) -> None:
    element = _resolve_element(client, target)
    element_type = element["type"].upper()
    if element_type != "PARTSTUDIO":
        if element_type == "ASSEMBLY":
            raise OnshapeError(
                "The pasted URL points to an Assembly tab. Phase 1 only supports Part Studio URLs because an assembly "
                "does not identify a single editable source part automatically. Open the source Part Studio tab for the "
                "part you want to remediate and paste that URL instead."
            )
        raise OnshapeError(
            f"The pasted URL points to element type '{element['type'] or 'unknown'}'. Phase 1 only supports Part Studio tabs."
        )
    parts_payload = client.get_parts(target)
    if not isinstance(parts_payload, list):
        raise OnshapeError("Unexpected Onshape parts listing response.")
    if len(parts_payload) <= 1:
        return
    part_names = []
    for row in parts_payload[:10]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip() or str(row.get("partId", "")).strip() or "(unnamed part)"
        part_names.append(name)
    suffix = ""
    if len(parts_payload) > len(part_names):
        suffix = f" and {len(parts_payload) - len(part_names)} more"
    joined = ", ".join(part_names) if part_names else f"{len(parts_payload)} parts"
    raise OnshapeError(
        "The pasted Part Studio contains multiple parts. Phase 1 does not yet know which single part to export and remediate. "
        f"Open or isolate the target part first, or use a single-part Part Studio. Parts found: {joined}{suffix}."
    )


def _evaluate_step_export(step_path: str, cfg: Config, qty: int):
    shape = read_step(step_path)
    results = run_all_rules(shape, cfg)
    rule_multiplier = combined_rule_multiplier(results)
    hole_count = 0
    radius_count = 0
    for result in results:
        if _rule_id(result.name) == "R4":
            hole_count = result.detected_features
        if _rule_id(result.name) == "R1":
            radius_count = result.detected_features
    process_data = compute_part_process_data(
        shape,
        cfg,
        cfg.material_key,
        cfg.baseline_6061_mrr_mm3_per_min,
        cfg.material_billet_cost_eur_per_kg,
        rule_multiplier,
        hole_count,
        radius_count,
        qty,
    )
    return results, process_data


def _analysis_session_from_target(client: OnshapeClient, target: OnshapeTarget, cfg: Config, qty: int) -> AnalysisSession:
    features_payload = client.get_features(target, include_geometry_ids=True)
    supported = parse_supported_features(features_payload)
    traces = collect_feature_fingerprints(client, target, supported)
    step_path = export_partstudio_step(client, target)
    print_boot(str(step_path))
    results, process_data = _evaluate_step_export(str(step_path), cfg, qty)
    print_part_process_data(process_data)
    print_report(results, str(step_path))
    offender_records = _flatten_offenders(results)
    matches = match_offenders_to_candidates(offender_records, supported, traces)
    proposals = build_proposals(offender_records, matches)
    feature_candidates = _flatten_candidates(matches)
    session = AnalysisSession(
        session_id=new_session_id(),
        target=target,
        source_microversion=_features_payload_microversion(features_payload),
        export_path=str(step_path),
        offender_records=offender_records,
        feature_candidates=feature_candidates,
        proposals=proposals,
        audit_log=[],
    )
    append_audit(session, f"analyze exported {step_path}")
    return session


def _feature_payload_root(payload: Dict[str, object]) -> Dict[str, object]:
    if isinstance(payload.get("feature"), dict):
        return payload["feature"]  # type: ignore[index]
    return payload


def _feature_message(payload: Dict[str, object]) -> Dict[str, object]:
    root = _feature_payload_root(payload)
    if isinstance(root.get("message"), dict):
        return root["message"]  # type: ignore[index]
    return root


def _set_parameter_expression(feature_payload: Dict[str, object], parameter_id: str, expression: str) -> None:
    message = _feature_message(feature_payload)
    parameters = message.get("parameters", [])
    if not isinstance(parameters, list):
        raise OnshapeError("Unexpected feature payload: missing parameter list.")
    for row in parameters:
        if not isinstance(row, dict):
            continue
        param = row.get("message") if isinstance(row.get("message"), dict) else row
        if str(param.get("parameterId", "")).strip() != parameter_id:
            continue
        param["expression"] = expression
        return
    raise OnshapeError(f"Parameter '{parameter_id}' not found in feature payload.")


def _proposal_by_id(session: AnalysisSession, proposal_id: str) -> RemediationProposal:
    for proposal in session.proposals:
        if proposal.proposal_id == proposal_id:
            return proposal
    raise OnshapeError(f"Proposal '{proposal_id}' not found in session {session.session_id}.")


def _add_common_rule_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--min-radius", dest="min_radius", type=float, default=None)
    parser.add_argument("--max-pocket-ratio", dest="max_pocket_ratio", type=float, default=None)
    parser.add_argument("--min-wall", dest="min_wall", type=float, default=None)
    parser.add_argument("--max-hole-ratio", dest="max_hole_ratio", type=float, default=None)
    parser.add_argument("--max-setups", dest="max_setups", type=int, default=None)
    parser.add_argument("--max-tool-depth-ratio", dest="max_tool_depth_ratio", type=float, default=None)
    parser.add_argument("--material", choices=material_keys(), default=None)
    parser.add_argument("--baseline-6061-mrr", dest="baseline_6061_mrr", type=float, default=None)
    parser.add_argument("--machine-hourly-rate-3-axis-eur", dest="machine_hourly_rate_3_axis_eur", type=float, default=None)
    parser.add_argument("--machine-hourly-rate-5-axis-eur", dest="machine_hourly_rate_5_axis_eur", type=float, default=None)
    parser.add_argument("--material-billet-cost-eur-per-kg", dest="material_billet_cost_eur_per_kg", type=float, default=None)
    parser.add_argument("--surface-penalty-slope", dest="surface_penalty_slope", type=float, default=None)
    parser.add_argument("--surface-penalty-max-multiplier", dest="surface_penalty_max_multiplier", type=float, default=None)
    parser.add_argument("--complexity-penalty-per-face", dest="complexity_penalty_per_face", type=float, default=None)
    parser.add_argument("--complexity-penalty-max-multiplier", dest="complexity_penalty_max_multiplier", type=float, default=None)
    parser.add_argument("--complexity-baseline-faces", dest="complexity_baseline_faces", type=int, default=None)
    parser.add_argument("--hole-count-penalty-per-feature", dest="hole_count_penalty_per_feature", type=float, default=None)
    parser.add_argument("--hole-count-penalty-max-multiplier", dest="hole_count_penalty_max_multiplier", type=float, default=None)
    parser.add_argument("--radius-count-penalty-per-feature", dest="radius_count_penalty_per_feature", type=float, default=None)
    parser.add_argument("--radius-count-penalty-max-multiplier", dest="radius_count_penalty_max_multiplier", type=float, default=None)
    parser.add_argument("--qty-learning-rate", dest="qty_learning_rate", type=float, default=None)
    parser.add_argument("--qty-factor-floor", dest="qty_factor_floor", type=float, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Onshape CLI prototype for CNC-DFM remediation.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Export an Onshape Part Studio, run DFM, and store proposals.")
    analyze.add_argument("target", nargs="?", help="Full Onshape workspace Part Studio URL.")
    analyze.add_argument("--url", default=None, help="Full Onshape workspace Part Studio URL.")
    analyze.add_argument("--did", default=None)
    analyze.add_argument("--wid", default=None)
    analyze.add_argument("--eid", default=None)
    analyze.add_argument("--configuration", default=None)
    _add_common_rule_args(analyze)

    propose = subparsers.add_parser("propose", help="List stored proposals for a prior Onshape analysis session.")
    propose.add_argument("--session", required=True)

    apply_cmd = subparsers.add_parser("apply", help="Apply one stored remediation proposal and rerun DFM.")
    apply_cmd.add_argument("--session", required=True)
    apply_cmd.add_argument("--proposal", required=True)
    _add_common_rule_args(apply_cmd)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()

        if args.command == "analyze":
            client = OnshapeClient.from_env()
            cfg = build_cfg(args)
            target = _target_from_args(args)
            session = _analysis_session_from_target(client, target, cfg, args.qty)
            path = save_session(session)
            print(f"SESSION  {session.session_id}")
            print(f"SAVED    {path}")
            _print_proposals(session.proposals)
            return 0

        if args.command == "propose":
            session = load_session(args.session)
            print(f"SESSION  {session.session_id}")
            print(f"TARGET   did={session.target.did} wid={session.target.wid} eid={session.target.eid}")
            _print_proposals(session.proposals)
            return 0

        if args.command == "apply":
            client = OnshapeClient.from_env()
            session = load_session(args.session)
            proposal = _proposal_by_id(session, args.proposal)
            cfg = build_cfg(args)
            current_microversion = client.get_current_microversion(session.target)
            if session.source_microversion and current_microversion and current_microversion != session.source_microversion:
                append_audit(
                    session,
                    f"stale source microversion detected: expected {session.source_microversion}, found {current_microversion}",
                )
            feature_payload = client.get_feature(session.target, proposal.feature_id)
            _set_parameter_expression(feature_payload, proposal.parameter_id or "", proposal.after)
            client.update_feature(session.target, proposal.feature_id, feature_payload)
            append_audit(session, f"applied {proposal.proposal_id} to feature {proposal.feature_id}: {proposal.before} -> {proposal.after}")
            step_path = export_partstudio_step(client, session.target, prefix=f"onshape-{session.session_id}-")
            session.export_path = str(step_path)
            updated_features = client.get_features(session.target, include_geometry_ids=True)
            session.source_microversion = _features_payload_microversion(updated_features)
            save_session(session)
            print_boot(str(step_path))
            results, process_data = _evaluate_step_export(str(step_path), cfg, args.qty)
            print_part_process_data(process_data)
            print_report(results, str(step_path))
            print(f"APPLIED  {proposal.proposal_id}")
            print(f"SESSION  {session.session_id}")
            return 0

        raise OnshapeError(f"Unsupported command: {args.command}")
    except (FileNotFoundError, OnshapeError, RuntimeError) as exc:
        print(f"ERROR    {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
