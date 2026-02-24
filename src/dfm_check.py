#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import List

from OCC.Core.TopoDS import TopoDS_Shape

from dfm_geometry import read_step
from dfm_models import Config, RuleResult
from dfm_terminal import print_boot, print_report
from rules import (
    evaluate_deep_pocket_ratio,
    evaluate_hole_depth_vs_diameter,
    evaluate_internal_corner_radius,
    evaluate_multiple_setup_faces,
    evaluate_thin_walls,
)


def run_all_rules(shape: TopoDS_Shape, cfg: Config) -> List[RuleResult]:
    return [
        evaluate_internal_corner_radius(shape, cfg),
        evaluate_deep_pocket_ratio(shape, cfg),
        evaluate_thin_walls(shape, cfg),
        evaluate_hole_depth_vs_diameter(shape, cfg),
        evaluate_multiple_setup_faces(shape, cfg),
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI DFM checker for STEP files (pythonOCC).")
    parser.add_argument("step_file", help="Path to input STEP file")
    parser.add_argument("--min-radius", type=float, default=1.0, help="Rule 1 min internal radius (mm)")
    parser.add_argument("--max-pocket-ratio", type=float, default=4.0, help="Rule 2 max pocket depth ratio")
    parser.add_argument("--min-wall", type=float, default=1.0, help="Rule 3 min wall thickness (mm)")
    parser.add_argument("--max-hole-ratio", type=float, default=6.0, help="Rule 4 max hole depth/diameter ratio")
    parser.add_argument("--max-setups", type=int, default=2, help="Rule 5 max setup faces/axes")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = Config(
        min_internal_corner_radius_mm=args.min_radius,
        max_pocket_depth_ratio=args.max_pocket_ratio,
        min_wall_thickness_mm=args.min_wall,
        max_hole_depth_to_diameter=args.max_hole_ratio,
        max_setups=args.max_setups,
    )
    print_boot(args.step_file)
    shape = read_step(args.step_file)
    results = run_all_rules(shape, cfg)
    print_report(results, args.step_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
