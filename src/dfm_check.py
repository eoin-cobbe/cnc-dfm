#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from typing import List, Set

from OCC.Core.TopoDS import TopoDS_Shape

from dfm_geometry import read_step, shape_bbox, shape_surface_area_mm2, shape_volume_mm3
from dfm_materials import get_material, material_keys
from dfm_models import Config, PartProcessData, RuleResult
from dfm_terminal import print_boot, print_part_process_data, print_report
from rules.rule5_multiple_setup_faces import required_setup_directions
from rules import (
    evaluate_missing_internal_relief,
    evaluate_deep_pocket_ratio,
    evaluate_hole_depth_vs_diameter,
    evaluate_internal_corner_radius,
    evaluate_multiple_setup_faces,
    evaluate_tool_depth_to_diameter,
    evaluate_thin_walls,
)


def run_all_rules(shape: TopoDS_Shape, cfg: Config) -> List[RuleResult]:
    rule0 = evaluate_missing_internal_relief(shape, cfg)
    if not rule0.passed:
        return [rule0]
    return [
        rule0,
        evaluate_internal_corner_radius(shape, cfg),
        evaluate_deep_pocket_ratio(shape, cfg),
        evaluate_thin_walls(shape, cfg),
        evaluate_hole_depth_vs_diameter(shape, cfg),
        evaluate_multiple_setup_faces(shape, cfg),
        evaluate_tool_depth_to_diameter(shape, cfg),
    ]


def combined_rule_multiplier(results: List[RuleResult]) -> float:
    mult = 1.0
    for result in results:
        mult *= max(1.0, result.rule_multiplier)
    return mult


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI DFM checker for STEP files (pythonOCC).")
    parser.add_argument("step_file", help="Path to input STEP file")
    parser.add_argument("--qty", type=int, default=1, help="Batch quantity for learning-curve scaling")
    parser.add_argument("--min-radius", type=float, default=1.0, help="Rule 1 min internal radius (mm)")
    parser.add_argument("--max-pocket-ratio", type=float, default=4.0, help="Rule 2 max pocket depth ratio")
    parser.add_argument("--min-wall", type=float, default=1.0, help="Rule 3 min wall thickness (mm)")
    parser.add_argument("--max-hole-ratio", type=float, default=6.0, help="Rule 4 max hole depth/diameter ratio")
    parser.add_argument("--max-setups", type=int, default=2, help="Rule 5 max setup faces/axes")
    parser.add_argument("--tool-diameter", type=float, default=6.0, help="Rule 6 tool diameter (mm)")
    parser.add_argument(
        "--max-tool-depth-ratio",
        type=float,
        default=3.0,
        help="Rule 6 max pocket depth/tool diameter ratio",
    )
    parser.add_argument(
        "--material",
        choices=material_keys(),
        default="304_stainless_steel",
        help="Part material key",
    )
    parser.add_argument(
        "--baseline-6061-mrr",
        type=float,
        default=20000.0,
        help="Baseline 6061 roughing MRR (mm^3/min) used to estimate other materials",
    )
    parser.add_argument(
        "--machine-hourly-rate-3-axis-eur",
        type=float,
        default=50.0,
        help="3-axis machine hourly rate in EUR/hr for roughing cost estimate",
    )
    parser.add_argument(
        "--machine-hourly-rate-5-axis-eur",
        type=float,
        default=100.0,
        help="5-axis machine hourly rate in EUR/hr for roughing cost estimate",
    )
    parser.add_argument(
        "--material-billet-cost-eur-per-kg",
        type=float,
        default=None,
        help="Billet cost in EUR/kg for selected material (defaults to material baseline)",
    )
    parser.add_argument(
        "--surface-penalty-slope",
        type=float,
        default=0.15,
        help="Surface complexity slope for finish multiplier (time penalty)",
    )
    parser.add_argument(
        "--surface-penalty-max-multiplier",
        type=float,
        default=1.5,
        help="Maximum finish multiplier from surface complexity",
    )
    parser.add_argument(
        "--hole-count-penalty-per-feature",
        type=float,
        default=0.01,
        help="Penalty per detected hole feature (adds to multiplier)",
    )
    parser.add_argument(
        "--hole-count-penalty-max-multiplier",
        type=float,
        default=1.5,
        help="Maximum hole-count multiplier",
    )
    parser.add_argument(
        "--radius-count-penalty-per-feature",
        type=float,
        default=0.005,
        help="Penalty per detected internal radius feature (adds to multiplier)",
    )
    parser.add_argument(
        "--radius-count-penalty-max-multiplier",
        type=float,
        default=1.5,
        help="Maximum radius-count multiplier",
    )
    parser.add_argument(
        "--qty-learning-rate",
        type=float,
        default=0.76,
        help="Learning rate for quantity scaling (e.g., 0.90 means 10%% reduction per quantity doubling)",
    )
    parser.add_argument(
        "--qty-factor-floor",
        type=float,
        default=0.29,
        help="Minimum quantity multiplier floor",
    )
    return parser


def compute_part_process_data(
    shape: TopoDS_Shape,
    cfg: Config,
    material_key: str,
    baseline_6061_mrr_mm3_per_min: float,
    material_billet_cost_eur_per_kg: float | None,
    rule_multiplier: float,
    hole_count: int,
    radius_count: int,
    qty: int,
) -> PartProcessData:
    def _is_opposite_pair(setup_keys: Set[str]) -> bool:
        if len(setup_keys) != 2:
            return False
        axes = {key[0] for key in setup_keys}
        sides = {key[1] for key in setup_keys}
        return len(axes) == 1 and sides == {"+", "-"}

    volume_mm3 = shape_volume_mm3(shape)
    part_surface_area_mm2 = shape_surface_area_mm2(shape)
    part_bbox_x_mm, part_bbox_y_mm, part_bbox_z_mm = shape_bbox(shape)
    bbox_volume_mm3 = part_bbox_x_mm * part_bbox_y_mm * part_bbox_z_mm
    stock_bbox_x_mm = part_bbox_x_mm + 10.0
    stock_bbox_y_mm = part_bbox_y_mm + 10.0
    stock_bbox_z_mm = part_bbox_z_mm + 10.0
    stock_volume_mm3 = stock_bbox_x_mm * stock_bbox_y_mm * stock_bbox_z_mm
    removed_volume_mm3 = max(0.0, stock_volume_mm3 - volume_mm3)
    bbox_surface_area_mm2 = 2.0 * (
        (part_bbox_x_mm * part_bbox_y_mm)
        + (part_bbox_x_mm * part_bbox_z_mm)
        + (part_bbox_y_mm * part_bbox_z_mm)
    )
    part_sav_ratio = part_surface_area_mm2 / volume_mm3 if volume_mm3 > 0.0 else 0.0
    bbox_sav_ratio = bbox_surface_area_mm2 / bbox_volume_mm3 if bbox_volume_mm3 > 0.0 else 0.0
    surface_complexity_ratio = (
        part_sav_ratio / bbox_sav_ratio if bbox_sav_ratio > 0.0 else 1.0
    )
    finish_multiplier = 1.0 + cfg.surface_penalty_slope * (surface_complexity_ratio - 1.0)
    finish_multiplier = max(1.0, min(finish_multiplier, cfg.surface_penalty_max_multiplier))
    material = get_material(material_key)
    ref_6061 = get_material("6061_aluminium")
    billet_cost_eur_per_kg = (
        material_billet_cost_eur_per_kg
        if material_billet_cost_eur_per_kg is not None
        else material.baseline_billet_cost_eur_per_kg
    )
    material_fixed_cost_eur = material.baseline_fixed_stock_cost_eur
    volume_m3 = volume_mm3 * 1e-9
    stock_volume_m3 = stock_volume_mm3 * 1e-9
    mass_kg = volume_m3 * material.density_kg_per_m3
    stock_mass_kg = stock_volume_m3 * material.density_kg_per_m3
    material_stock_cost_eur = material_fixed_cost_eur + (stock_mass_kg * billet_cost_eur_per_kg)
    hole_count_multiplier = min(
        cfg.hole_count_penalty_max_multiplier,
        1.0 + (cfg.hole_count_penalty_per_feature * max(0, hole_count)),
    )
    radius_count_multiplier = min(
        cfg.radius_count_penalty_max_multiplier,
        1.0 + (cfg.radius_count_penalty_per_feature * max(0, radius_count)),
    )
    setup_keys = required_setup_directions(shape, cfg)
    setup_text = ", ".join(sorted(setup_keys)) if setup_keys else "none"
    is_flip_only = len(setup_keys) <= 1 or _is_opposite_pair(setup_keys)
    machine_type = "3-axis" if is_flip_only else "5-axis"
    machine_hourly_rate_eur = (
        cfg.machine_hourly_rate_3_axis_eur if machine_type == "3-axis" else cfg.machine_hourly_rate_5_axis_eur
    )
    material_time_multiplier = ref_6061.machinability_percent / material.machinability_percent
    estimated_roughing_mrr_mm3_per_min = baseline_6061_mrr_mm3_per_min / material_time_multiplier
    base_roughing_time_min = removed_volume_mm3 / baseline_6061_mrr_mm3_per_min
    roughing_time_min = base_roughing_time_min * material_time_multiplier
    learning_rate = max(1e-6, min(cfg.qty_learning_rate, 1.0))
    qty_factor_floor = max(1e-6, min(cfg.qty_factor_floor, 1.0))
    qty_safe = max(1, qty)
    learning_exponent = math.log(learning_rate, 2)
    qty_multiplier = max(qty_factor_floor, qty_safe ** learning_exponent)
    total_time_multiplier = (
        finish_multiplier
        * material_time_multiplier
        * rule_multiplier
        * hole_count_multiplier
        * radius_count_multiplier
    )
    base_machining_time_min = (
        roughing_time_min
        * finish_multiplier
        * rule_multiplier
        * hole_count_multiplier
        * radius_count_multiplier
    )
    machining_time_min = base_machining_time_min * qty_multiplier
    roughing_cost = (roughing_time_min / 60.0) * machine_hourly_rate_eur
    machining_cost = (machining_time_min / 60.0) * machine_hourly_rate_eur
    base_machining_cost = (base_machining_time_min / 60.0) * machine_hourly_rate_eur
    total_estimated_cost_eur = (material_stock_cost_eur + base_machining_cost) * qty_multiplier
    batch_total_estimated_cost_eur = total_estimated_cost_eur * qty_safe
    return PartProcessData(
        material_key=material.key,
        material_label=material.label,
        part_bbox_x_mm=part_bbox_x_mm,
        part_bbox_y_mm=part_bbox_y_mm,
        part_bbox_z_mm=part_bbox_z_mm,
        stock_bbox_x_mm=stock_bbox_x_mm,
        stock_bbox_y_mm=stock_bbox_y_mm,
        stock_bbox_z_mm=stock_bbox_z_mm,
        volume_mm3=volume_mm3,
        stock_volume_mm3=stock_volume_mm3,
        removed_volume_mm3=removed_volume_mm3,
        part_surface_area_mm2=part_surface_area_mm2,
        part_sav_ratio=part_sav_ratio,
        bbox_sav_ratio=bbox_sav_ratio,
        surface_complexity_ratio=surface_complexity_ratio,
        finish_multiplier=finish_multiplier,
        density_kg_per_m3=material.density_kg_per_m3,
        mass_kg=mass_kg,
        stock_mass_kg=stock_mass_kg,
        material_billet_cost_eur_per_kg=billet_cost_eur_per_kg,
        material_fixed_cost_eur=material_fixed_cost_eur,
        material_stock_cost_eur=material_stock_cost_eur,
        material_billet_cost_source=material.baseline_billet_cost_source,
        material_fixed_cost_source=material.baseline_fixed_stock_cost_source,
        required_setup_directions=setup_text,
        machine_type=machine_type,
        hole_count=hole_count,
        hole_count_multiplier=hole_count_multiplier,
        radius_count=radius_count,
        radius_count_multiplier=radius_count_multiplier,
        machinability_percent=material.machinability_percent,
        machinability_source=material.machinability_source,
        baseline_6061_mrr_mm3_per_min=baseline_6061_mrr_mm3_per_min,
        material_time_multiplier=material_time_multiplier,
        rule_multiplier=rule_multiplier,
        total_time_multiplier=total_time_multiplier,
        qty=qty_safe,
        qty_multiplier=qty_multiplier,
        estimated_roughing_mrr_mm3_per_min=estimated_roughing_mrr_mm3_per_min,
        roughing_time_min=roughing_time_min,
        base_machining_time_min=base_machining_time_min,
        machining_time_min=machining_time_min,
        machine_hourly_rate_eur=machine_hourly_rate_eur,
        roughing_cost=roughing_cost,
        machining_cost=machining_cost,
        total_estimated_cost_eur=total_estimated_cost_eur,
        batch_total_estimated_cost_eur=batch_total_estimated_cost_eur,
    )


def main() -> int:
    args = build_arg_parser().parse_args()
    selected_material = get_material(args.material)
    resolved_billet_cost = (
        args.material_billet_cost_eur_per_kg
        if args.material_billet_cost_eur_per_kg is not None
        else selected_material.baseline_billet_cost_eur_per_kg
    )
    cfg = Config(
        min_internal_corner_radius_mm=args.min_radius,
        max_pocket_depth_ratio=args.max_pocket_ratio,
        tool_diameter_mm=args.tool_diameter,
        max_tool_depth_to_diameter_ratio=args.max_tool_depth_ratio,
        min_wall_thickness_mm=args.min_wall,
        max_hole_depth_to_diameter=args.max_hole_ratio,
        max_setups=args.max_setups,
        material_key=args.material,
        baseline_6061_mrr_mm3_per_min=args.baseline_6061_mrr,
        machine_hourly_rate_3_axis_eur=args.machine_hourly_rate_3_axis_eur,
        machine_hourly_rate_5_axis_eur=args.machine_hourly_rate_5_axis_eur,
        material_billet_cost_eur_per_kg=resolved_billet_cost,
        surface_penalty_slope=args.surface_penalty_slope,
        surface_penalty_max_multiplier=args.surface_penalty_max_multiplier,
        hole_count_penalty_per_feature=args.hole_count_penalty_per_feature,
        hole_count_penalty_max_multiplier=args.hole_count_penalty_max_multiplier,
        radius_count_penalty_per_feature=args.radius_count_penalty_per_feature,
        radius_count_penalty_max_multiplier=args.radius_count_penalty_max_multiplier,
        qty_learning_rate=args.qty_learning_rate,
        qty_factor_floor=args.qty_factor_floor,
    )
    print_boot(args.step_file)
    shape = read_step(args.step_file)
    results = run_all_rules(shape, cfg)
    rule_multiplier = combined_rule_multiplier(results)
    hole_count = 0
    radius_count = 0
    for result in results:
        if "Rule 4" in result.name:
            hole_count = result.detected_features
        if "Rule 1" in result.name:
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
        args.qty,
    )
    print_part_process_data(process_data)
    print_report(results, args.step_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
