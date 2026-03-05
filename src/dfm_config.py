#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dfm_materials import DEFAULT_MATERIAL_KEY, MATERIAL_OPTIONS, get_material

DEFAULTS = {
    "min_radius": 1.0,
    "max_pocket_ratio": 4.0,
    "tool_diameter": 6.0,
    "max_tool_depth_ratio": 3.0,
    "min_wall": 1.0,
    "max_hole_ratio": 6.0,
    "max_setups": 2,
    "material": DEFAULT_MATERIAL_KEY,
    "baseline_6061_mrr": 120000.0,
    "machine_hourly_rate_3_axis_eur": 50.0,
    "machine_hourly_rate_5_axis_eur": 100.0,
    "material_billet_cost_eur_per_kg": get_material(DEFAULT_MATERIAL_KEY).baseline_billet_cost_eur_per_kg,
    "surface_penalty_slope": 0.15,
    "surface_penalty_max_multiplier": 1.5,
    "hole_count_penalty_per_feature": 0.01,
    "hole_count_penalty_max_multiplier": 1.5,
    "radius_count_penalty_per_feature": 0.005,
    "radius_count_penalty_max_multiplier": 1.5,
    "qty_learning_rate": 0.90,
    "qty_factor_floor": 0.75,
    "material_qty_discount_rate": 0.97,
    "material_qty_discount_floor": 0.85,
}

FIELDS: List[Tuple[str, str, str, str]] = [
    ("min_radius", "Rule 1", "Min internal corner radius (mm)", "float"),
    ("max_pocket_ratio", "Rule 2", "Max pocket depth ratio", "float"),
    ("min_wall", "Rule 3", "Min wall thickness (mm)", "float"),
    ("max_hole_ratio", "Rule 4", "Max hole depth/diameter ratio", "float"),
    ("max_setups", "Rule 5", "Max setup faces/axes", "int"),
    ("tool_diameter", "Rule 6", "Tool diameter (mm)", "float"),
    ("max_tool_depth_ratio", "Rule 6", "Max pocket depth/tool diameter ratio", "float"),
    ("material", "Part", "Material", "material"),
    ("material_billet_cost_eur_per_kg", "Part", "Material billet cost (EUR/kg)", "float"),
    ("baseline_6061_mrr", "Part", "Baseline 6061 roughing MRR (mm^3/min)", "float"),
    ("machine_hourly_rate_3_axis_eur", "Part", "3-axis machine hourly rate (EUR/hr)", "float"),
    ("machine_hourly_rate_5_axis_eur", "Part", "5-axis machine hourly rate (EUR/hr)", "float"),
    ("surface_penalty_slope", "Part", "Surface penalty slope", "float"),
    ("surface_penalty_max_multiplier", "Part", "Surface penalty max multiplier", "float"),
    ("hole_count_penalty_per_feature", "Part", "Hole-count penalty per feature", "float"),
    ("hole_count_penalty_max_multiplier", "Part", "Hole-count penalty max multiplier", "float"),
    ("radius_count_penalty_per_feature", "Part", "Radius-count penalty per feature", "float"),
    ("radius_count_penalty_max_multiplier", "Part", "Radius-count penalty max multiplier", "float"),
    ("qty_learning_rate", "Part", "Quantity learning rate", "float"),
    ("qty_factor_floor", "Part", "Quantity factor floor", "float"),
    ("material_qty_discount_rate", "Part", "Material qty discount rate", "float"),
    ("material_qty_discount_floor", "Part", "Material qty discount floor", "float"),
]

CLI_FLAGS = {
    "min_radius": "--min-radius",
    "max_pocket_ratio": "--max-pocket-ratio",
    "tool_diameter": "--tool-diameter",
    "max_tool_depth_ratio": "--max-tool-depth-ratio",
    "min_wall": "--min-wall",
    "max_hole_ratio": "--max-hole-ratio",
    "max_setups": "--max-setups",
    "material": "--material",
    "material_billet_cost_eur_per_kg": "--material-billet-cost-eur-per-kg",
    "baseline_6061_mrr": "--baseline-6061-mrr",
    "machine_hourly_rate_3_axis_eur": "--machine-hourly-rate-3-axis-eur",
    "machine_hourly_rate_5_axis_eur": "--machine-hourly-rate-5-axis-eur",
    "surface_penalty_slope": "--surface-penalty-slope",
    "surface_penalty_max_multiplier": "--surface-penalty-max-multiplier",
    "hole_count_penalty_per_feature": "--hole-count-penalty-per-feature",
    "hole_count_penalty_max_multiplier": "--hole-count-penalty-max-multiplier",
    "radius_count_penalty_per_feature": "--radius-count-penalty-per-feature",
    "radius_count_penalty_max_multiplier": "--radius-count-penalty-max-multiplier",
    "qty_learning_rate": "--qty-learning-rate",
    "qty_factor_floor": "--qty-factor-floor",
    "material_qty_discount_rate": "--material-qty-discount-rate",
    "material_qty_discount_floor": "--material-qty-discount-floor",
}

LOGO_LINES = [
    " ######  ##    ##  ######          ######   ######## ##     ## ",
    "##    ## ###   ## ##    ##        ##    ##  ##       ###   ### ",
    "##       ####  ## ##              ##    ##  ##       #### #### ",
    "##       ## ## ## ##              ##    ##  ######   ## ### ## ",
    "##       ##  #### ##              ##    ##  ##       ##  #  ## ",
    "##    ## ##   ### ##    ##        ##    ##  ##       ##     ## ",
    " ######  ##    ##  ######          ######   ##       ##     ## ",
]


def config_path() -> Path:
    override = os.getenv("CNC_DFM_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / "cache" / "dfm_config.json"


def load_config() -> Dict[str, Any]:
    path = config_path()
    if not path.exists():
        return DEFAULTS.copy()
    try:
        data = json.loads(path.read_text())
    except Exception:
        return DEFAULTS.copy()

    merged = DEFAULTS.copy()
    # Backward compatibility:
    # - old key was minute-based (`machine_minute_cost`)
    # - old key was unified hourly (`machine_hourly_rate_eur`)
    if "machine_hourly_rate_3_axis_eur" not in data and "machine_hourly_rate_5_axis_eur" not in data:
        if "machine_hourly_rate_eur" in data:
            try:
                legacy_hourly = float(data["machine_hourly_rate_eur"])
                merged["machine_hourly_rate_3_axis_eur"] = legacy_hourly
                merged["machine_hourly_rate_5_axis_eur"] = DEFAULTS["machine_hourly_rate_5_axis_eur"]
            except Exception:
                pass
    if "machine_hourly_rate_3_axis_eur" not in data and "machine_hourly_rate_5_axis_eur" not in data and "machine_minute_cost" in data:
        try:
            legacy = float(data["machine_minute_cost"])
            converted = legacy * 60.0 if legacy <= 10.0 else legacy
            merged["machine_hourly_rate_3_axis_eur"] = converted
            merged["machine_hourly_rate_5_axis_eur"] = DEFAULTS["machine_hourly_rate_5_axis_eur"]
        except Exception:
            pass
    for key in DEFAULTS:
        if key in data:
            merged[key] = data[key]
    if "material_billet_cost_eur_per_kg" not in data:
        selected = get_material(str(merged["material"]))
        merged["material_billet_cost_eur_per_kg"] = selected.baseline_billet_cost_eur_per_kg
    return merged


def load_saved_only() -> Dict[str, Any] | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None

    merged = DEFAULTS.copy()
    # Backward compatibility:
    # - old key was minute-based (`machine_minute_cost`)
    # - old key was unified hourly (`machine_hourly_rate_eur`)
    if "machine_hourly_rate_3_axis_eur" not in data and "machine_hourly_rate_5_axis_eur" not in data:
        if "machine_hourly_rate_eur" in data:
            try:
                legacy_hourly = float(data["machine_hourly_rate_eur"])
                merged["machine_hourly_rate_3_axis_eur"] = legacy_hourly
                merged["machine_hourly_rate_5_axis_eur"] = DEFAULTS["machine_hourly_rate_5_axis_eur"]
            except Exception:
                pass
    if "machine_hourly_rate_3_axis_eur" not in data and "machine_hourly_rate_5_axis_eur" not in data and "machine_minute_cost" in data:
        try:
            legacy = float(data["machine_minute_cost"])
            converted = legacy * 60.0 if legacy <= 10.0 else legacy
            merged["machine_hourly_rate_3_axis_eur"] = converted
            merged["machine_hourly_rate_5_axis_eur"] = DEFAULTS["machine_hourly_rate_5_axis_eur"]
        except Exception:
            pass
    for key in DEFAULTS:
        if key in data:
            merged[key] = data[key]
    if "material_billet_cost_eur_per_kg" not in data:
        selected = get_material(str(merged["material"]))
        merged["material_billet_cost_eur_per_kg"] = selected.baseline_billet_cost_eur_per_kg
    return merged


def validate_value(key: str, kind: str, value: str):
    if kind == "material":
        return get_material(value).key
    if kind == "int":
        parsed = int(value)
        if parsed < 1:
            raise ValueError(f"{key} must be >= 1")
        return parsed
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{key} must be > 0")
    if key == "qty_learning_rate" and parsed > 1.0:
        raise ValueError(f"{key} must be <= 1.0")
    if key == "qty_factor_floor" and parsed > 1.0:
        raise ValueError(f"{key} must be <= 1.0")
    if key == "material_qty_discount_rate" and parsed > 1.0:
        raise ValueError(f"{key} must be <= 1.0")
    if key == "material_qty_discount_floor" and parsed > 1.0:
        raise ValueError(f"{key} must be <= 1.0")
    return parsed


def save_config(cfg: Dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")


def prompt_value(rule: str, label: str, key: str, kind: str, current):
    if kind == "material":
        print("")
        print(f"{rule} | {label} [{get_material(str(current)).label}]")
        for idx, mat in enumerate(MATERIAL_OPTIONS, start=1):
            print(f"  {idx}) {mat.label}")
        while True:
            raw = input("Select material number (Enter keeps current): ").strip()
            if raw == "":
                return current
            if raw.isdigit():
                selected = int(raw)
                if 1 <= selected <= len(MATERIAL_OPTIONS):
                    return MATERIAL_OPTIONS[selected - 1].key
            print("Invalid value: enter one of the listed material numbers.")

    while True:
        raw = input(f"{rule} | {label} [{current}]: ").strip()
        if raw == "":
            return current
        try:
            return validate_value(key, kind, raw)
        except Exception as exc:
            print(f"Invalid value: {exc}")


def run_wizard() -> int:
    cfg = load_config()

    print("")
    print("")
    for line in LOGO_LINES:
        print(line)
    print("")
    print("")
    print("+----------------------------------------------------------------+")
    print("| CNC-DFM CONFIG SETUP                                           |")
    print("+----------------------------------------------------------------+")
    print("Set thresholds for rules R1-R6. Press Enter to keep current value.")
    print("")

    updated: Dict[str, Any] = {}
    for key, rule, label, kind in FIELDS:
        if key == "material_billet_cost_eur_per_kg":
            selected_key = str(updated.get("material", cfg["material"]))
            selected = get_material(selected_key)
            # If material changed in this wizard run, start from selected-material baseline.
            current_cost = cfg[key]
            if selected_key != str(cfg["material"]):
                current_cost = selected.baseline_billet_cost_eur_per_kg
            updated[key] = prompt_value(rule, f"{label} [{selected.label}]", key, kind, current_cost)
            continue
        updated[key] = prompt_value(rule, label, key, kind, cfg[key])

    save_config(updated)

    print("")
    print("+----------------------------------------------------------------+")
    print("| CONFIG SAVED                                                   |")
    print("+----------------------------------------------------------------+")
    for key, rule, label, _kind in FIELDS:
        if key == "material":
            print(f"{rule}: {label} = {get_material(str(updated[key])).label}")
            continue
        if key == "material_billet_cost_eur_per_kg":
            selected = get_material(str(updated["material"]))
            print(f"{rule}: {label} [{selected.label}] = {updated[key]}")
            print(f"      Baseline source: {selected.baseline_billet_cost_source}")
            continue
        print(f"{rule}: {label} = {updated[key]}")
    print(f"Path: {config_path()}")
    print("Use 'run config' anytime to overwrite these values.")
    return 0


def print_args() -> int:
    cfg = load_saved_only()
    if cfg is None:
        return 0
    for key, _rule, _label, _kind in FIELDS:
        print(CLI_FLAGS[key])
        print(str(cfg[key]))
    return 0


def show_config() -> int:
    cfg = load_saved_only()
    if cfg is None:
        print(f"No saved config at {config_path()}")
        return 0
    print(json.dumps(cfg, indent=2))
    print(f"Path: {config_path()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CNC-DFM config manager")
    parser.add_argument("--wizard", action="store_true", help="Run interactive setup")
    parser.add_argument("--print-args", action="store_true", help="Print saved config as CLI args")
    parser.add_argument("--show", action="store_true", help="Show current saved config")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.print_args:
        return print_args()
    if args.show:
        return show_config()
    return run_wizard()


if __name__ == "__main__":
    raise SystemExit(main())
