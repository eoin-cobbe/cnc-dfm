#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from dfm_config import config_path, load_config, load_saved_only, normalize_config_payload, save_config_payload
from dfm_materials import MATERIAL_OPTIONS
from dfm_models import Config


def _emit_json(payload: Dict[str, Any]) -> int:
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _load_json_input(input_value: str) -> Dict[str, Any]:
    if input_value == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(input_value).read_text()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON input must be an object")
    return payload


def _config_to_model(cfg_values: Dict[str, Any]) -> Config:
    return Config(
        min_internal_corner_radius_mm=float(cfg_values["min_radius"]),
        max_pocket_depth_ratio=float(cfg_values["max_pocket_ratio"]),
        max_tool_depth_to_diameter_ratio=float(cfg_values["max_tool_depth_ratio"]),
        min_wall_thickness_mm=float(cfg_values["min_wall"]),
        max_hole_depth_to_diameter=float(cfg_values["max_hole_ratio"]),
        max_setups=int(cfg_values["max_setups"]),
        material_key=str(cfg_values["material"]),
        baseline_6061_mrr_mm3_per_min=float(cfg_values["baseline_6061_mrr"]),
        machine_hourly_rate_3_axis_eur=float(cfg_values["machine_hourly_rate_3_axis_eur"]),
        machine_hourly_rate_5_axis_eur=float(cfg_values["machine_hourly_rate_5_axis_eur"]),
        material_billet_cost_eur_per_kg=float(cfg_values["material_billet_cost_eur_per_kg"]),
        surface_penalty_slope=float(cfg_values["surface_penalty_slope"]),
        surface_penalty_max_multiplier=float(cfg_values["surface_penalty_max_multiplier"]),
        complexity_penalty_per_face=float(cfg_values["complexity_penalty_per_face"]),
        complexity_penalty_max_multiplier=float(cfg_values["complexity_penalty_max_multiplier"]),
        complexity_baseline_faces=int(cfg_values["complexity_baseline_faces"]),
        hole_count_penalty_per_feature=float(cfg_values["hole_count_penalty_per_feature"]),
        hole_count_penalty_max_multiplier=float(cfg_values["hole_count_penalty_max_multiplier"]),
        radius_count_penalty_per_feature=float(cfg_values["radius_count_penalty_per_feature"]),
        radius_count_penalty_max_multiplier=float(cfg_values["radius_count_penalty_max_multiplier"]),
        qty_learning_rate=float(cfg_values["qty_learning_rate"]),
        qty_factor_floor=float(cfg_values["qty_factor_floor"]),
    )


def _handle_config_show(_args: argparse.Namespace) -> int:
    saved = load_saved_only()
    effective = load_config()
    return _emit_json(
        {
            "configPath": str(config_path()),
            "hasSavedConfig": saved is not None,
            "values": effective,
        }
    )


def _handle_config_save(args: argparse.Namespace) -> int:
    payload = _load_json_input(args.json_input)
    saved = save_config_payload(payload, base=load_config())
    return _emit_json(
        {
            "configPath": str(config_path()),
            "hasSavedConfig": True,
            "values": saved,
        }
    )


def _handle_materials(_args: argparse.Namespace) -> int:
    return _emit_json(
        {
            "materials": [asdict(material) for material in MATERIAL_OPTIONS],
        }
    )


def _handle_health(_args: argparse.Namespace) -> int:
    analysis_runtime = {"available": True}
    try:
        import dfm_check  # noqa: F401
    except Exception as exc:
        analysis_runtime = {
            "available": False,
            "errorType": exc.__class__.__name__,
            "message": str(exc),
        }

    return _emit_json(
        {
            "status": "ok",
            "apiVersion": 1,
            "configPath": str(config_path()),
            "configExists": config_path().exists(),
            "pythonExecutable": sys.executable,
            "platform": sys.platform,
            "cwd": os.getcwd(),
            "analysisRuntime": analysis_runtime,
        }
    )


def _handle_analyze(args: argparse.Namespace) -> int:
    from dfm_check import analyze_step_file

    if args.qty < 1:
        raise ValueError("--qty must be >= 1")
    if args.save_config and args.config_input is None:
        raise ValueError("--save-config requires --config-input")

    cfg_values = load_config()
    if args.config_input is not None:
        payload = _load_json_input(args.config_input)
        if args.save_config:
            cfg_values = save_config_payload(payload, base=cfg_values)
        else:
            cfg_values = normalize_config_payload(payload, base=cfg_values)

    analysis = analyze_step_file(args.input, _config_to_model(cfg_values), args.qty)
    return _emit_json(asdict(analysis))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Machine-readable API for cnc-dfm app clients")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Read or update persisted config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    config_show = config_subparsers.add_parser("show", help="Show effective config as JSON")
    config_show.set_defaults(func=_handle_config_show)

    config_save = config_subparsers.add_parser("save", help="Save config values from JSON input")
    config_save.add_argument("--json-input", required=True, help="Path to JSON file or '-' for stdin")
    config_save.set_defaults(func=_handle_config_save)

    materials_parser = subparsers.add_parser("materials", help="List available materials")
    materials_parser.set_defaults(func=_handle_materials)

    health_parser = subparsers.add_parser("health", help="Show backend health and runtime info")
    health_parser.set_defaults(func=_handle_health)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a STEP file and return JSON")
    analyze_parser.add_argument("--input", required=True, help="Path to input STEP file")
    analyze_parser.add_argument("--qty", type=int, default=1, help="Batch quantity")
    analyze_parser.add_argument(
        "--config-input",
        help="Optional JSON config overrides path or '-' for stdin",
    )
    analyze_parser.add_argument(
        "--save-config",
        action="store_true",
        help="Persist config overrides before analysis",
    )
    analyze_parser.set_defaults(func=_handle_analyze)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        return _emit_json(
            {
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
            }
        ) or 1


if __name__ == "__main__":
    raise SystemExit(main())
