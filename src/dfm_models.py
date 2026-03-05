from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class RuleResult:
    name: str
    passed: bool
    summary: str
    details: str
    detected_features: int
    passed_features: int
    failed_features: int
    axis_breakdown: Optional[Dict[str, Tuple[int, int, int]]] = None
    minimum_detected: Optional[float] = None
    required_minimum: Optional[float] = None
    metric_label: Optional[str] = None
    average_detected: Optional[float] = None
    threshold: Optional[float] = None
    threshold_kind: Optional[str] = None  # "max" or "min"
    rule_multiplier: float = 1.0


@dataclass
class Config:
    min_internal_corner_radius_mm: float = 6.0
    max_pocket_depth_ratio: float = 4.0
    min_wall_thickness_mm: float = 1.0
    max_hole_depth_to_diameter: float = 6.0
    max_setups: int = 2
    tool_diameter_mm: float = 6.0
    max_tool_depth_to_diameter_ratio: float = 3.0
    normal_similarity_deg: float = 12.0
    material_key: str = "304_stainless_steel"
    baseline_6061_mrr_mm3_per_min: float = 120000.0
    machine_hourly_rate_3_axis_eur: float = 50.0
    machine_hourly_rate_5_axis_eur: float = 100.0
    material_billet_cost_eur_per_kg: float = 3.8
    surface_penalty_slope: float = 0.15
    surface_penalty_max_multiplier: float = 1.5
    hole_count_penalty_per_feature: float = 0.01
    hole_count_penalty_max_multiplier: float = 1.5
    radius_count_penalty_per_feature: float = 0.005
    radius_count_penalty_max_multiplier: float = 1.5
    qty_learning_rate: float = 0.90
    qty_factor_floor: float = 0.75
    material_qty_discount_rate: float = 0.97
    material_qty_discount_floor: float = 0.85


@dataclass
class PartProcessData:
    material_key: str
    material_label: str
    part_bbox_x_mm: float
    part_bbox_y_mm: float
    part_bbox_z_mm: float
    stock_bbox_x_mm: float
    stock_bbox_y_mm: float
    stock_bbox_z_mm: float
    volume_mm3: float
    stock_volume_mm3: float
    removed_volume_mm3: float
    part_surface_area_mm2: float
    part_sav_ratio: float
    bbox_sav_ratio: float
    surface_complexity_ratio: float
    finish_multiplier: float
    density_kg_per_m3: float
    mass_kg: float
    stock_mass_kg: float
    material_billet_cost_eur_per_kg: float
    material_stock_cost_eur: float
    material_discount_multiplier: float
    discounted_material_stock_cost_eur: float
    material_billet_cost_source: str
    required_setup_directions: str
    machine_type: str
    hole_count: int
    hole_count_multiplier: float
    radius_count: int
    radius_count_multiplier: float
    machinability_percent: float
    machinability_source: str
    baseline_6061_mrr_mm3_per_min: float
    material_time_multiplier: float
    rule_multiplier: float
    total_time_multiplier: float
    qty: int
    qty_multiplier: float
    estimated_roughing_mrr_mm3_per_min: float
    roughing_time_min: float
    base_machining_time_min: float
    machining_time_min: float
    machine_hourly_rate_eur: float
    roughing_cost: float
    machining_cost: float
    total_estimated_cost_eur: float
    batch_total_estimated_cost_eur: float
