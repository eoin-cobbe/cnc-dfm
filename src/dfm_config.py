#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULTS = {
    "min_radius": 1.0,
    "max_pocket_ratio": 4.0,
    "tool_diameter": 6.0,
    "max_tool_depth_ratio": 3.0,
    "min_wall": 1.0,
    "max_hole_ratio": 6.0,
    "max_setups": 2,
}

FIELDS: List[Tuple[str, str, str, str]] = [
    ("min_radius", "Rule 1", "Min internal corner radius (mm)", "float"),
    ("max_pocket_ratio", "Rule 2", "Max pocket depth ratio", "float"),
    ("min_wall", "Rule 3", "Min wall thickness (mm)", "float"),
    ("max_hole_ratio", "Rule 4", "Max hole depth/diameter ratio", "float"),
    ("max_setups", "Rule 5", "Max setup faces/axes", "int"),
    ("tool_diameter", "Rule 6", "Tool diameter (mm)", "float"),
    ("max_tool_depth_ratio", "Rule 6", "Max pocket depth/tool diameter ratio", "float"),
]

CLI_FLAGS = {
    "min_radius": "--min-radius",
    "max_pocket_ratio": "--max-pocket-ratio",
    "tool_diameter": "--tool-diameter",
    "max_tool_depth_ratio": "--max-tool-depth-ratio",
    "min_wall": "--min-wall",
    "max_hole_ratio": "--max-hole-ratio",
    "max_setups": "--max-setups",
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


def load_config() -> Dict[str, float]:
    path = config_path()
    if not path.exists():
        return DEFAULTS.copy()
    try:
        data = json.loads(path.read_text())
    except Exception:
        return DEFAULTS.copy()

    merged = DEFAULTS.copy()
    for key in DEFAULTS:
        if key in data:
            merged[key] = data[key]
    return merged


def load_saved_only() -> Dict[str, float] | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None

    merged = DEFAULTS.copy()
    for key in DEFAULTS:
        if key in data:
            merged[key] = data[key]
    return merged


def validate_value(key: str, kind: str, value: str):
    if kind == "int":
        parsed = int(value)
        if parsed < 1:
            raise ValueError(f"{key} must be >= 1")
        return parsed
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{key} must be > 0")
    return parsed


def save_config(cfg: Dict[str, float]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")


def prompt_value(rule: str, label: str, key: str, kind: str, current):
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

    updated: Dict[str, float] = {}
    for key, rule, label, kind in FIELDS:
        updated[key] = prompt_value(rule, label, key, kind, cfg[key])

    save_config(updated)

    print("")
    print("+----------------------------------------------------------------+")
    print("| CONFIG SAVED                                                   |")
    print("+----------------------------------------------------------------+")
    for key, rule, label, _kind in FIELDS:
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
