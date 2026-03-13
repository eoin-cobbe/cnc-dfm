from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class FeatureInsight:
    id: str
    summary: str
    highlight_kind: str = "point"
    axis: Optional[str] = None
    measured_value: Optional[float] = None
    target_value: Optional[float] = None
    units: Optional[str] = None
    anchor: Optional["Point3D"] = None
    segment_start: Optional["Point3D"] = None
    segment_end: Optional["Point3D"] = None
    overlay_mesh_paths: List[str] = field(default_factory=list)
    cost_impact: Optional["CostImpactRange"] = None


@dataclass
class Point3D:
    x: float
    y: float
    z: float


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
    feature_insights: List[FeatureInsight] = field(default_factory=list)
    all_feature_insights: List[FeatureInsight] = field(default_factory=list)


@dataclass
class Config:
    min_internal_corner_radius_mm: float = 2.0
    max_pocket_depth_ratio: float = 4.0
    min_wall_thickness_mm: float = 0.762
    max_hole_depth_to_diameter: float = 4.0
    max_setups: int = 2
    max_tool_depth_to_diameter_ratio: float = 2.0
    normal_similarity_deg: float = 12.0
    material_key: str = "304_stainless_steel"
    baseline_6061_mrr_mm3_per_min: float = 20000.0
    machine_hourly_rate_3_axis_eur: float = 50.0
    machine_hourly_rate_5_axis_eur: float = 100.0
    material_billet_cost_eur_per_kg: float = 11.49
    surface_penalty_slope: float = 0.15
    surface_penalty_max_multiplier: float = 1.5
    complexity_penalty_per_face: float = 0.002
    complexity_penalty_max_multiplier: float = 1.5
    complexity_baseline_faces: int = 6
    hole_count_penalty_per_feature: float = 0.01
    hole_count_penalty_max_multiplier: float = 1.5
    radius_count_penalty_per_feature: float = 0.005
    radius_count_penalty_max_multiplier: float = 1.5
    qty_learning_rate: float = 0.76
    qty_factor_floor: float = 0.29


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
    surface_area_ratio: float
    surface_area_multiplier: float
    surface_complexity_faces: int
    complexity_multiplier: float
    density_kg_per_m3: float
    mass_kg: float
    stock_mass_kg: float
    material_billet_cost_eur_per_kg: float
    material_fixed_cost_eur: float
    material_stock_cost_eur: float
    material_billet_cost_source: str
    material_fixed_cost_source: str
    required_setup_directions: str
    machine_type: str
    hole_count: int
    hole_count_multiplier: float
    radius_count: int
    radius_count_multiplier: float
    machinability_index: float
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


@dataclass
class AnalysisSummary:
    passed: bool
    total_rule_count: int
    passed_rule_count: int
    failed_rule_count: int
    rule_multiplier: float


@dataclass
class CostImpactBreakdown:
    label: str
    minimum_unit_savings_eur: float
    maximum_unit_savings_eur: float
    minimum_batch_savings_eur: float
    maximum_batch_savings_eur: float
    details: str = ""


@dataclass
class CostImpactRange:
    current_unit_cost_eur: float
    current_batch_cost_eur: float
    minimum_unit_savings_eur: float
    maximum_unit_savings_eur: float
    minimum_batch_savings_eur: float
    maximum_batch_savings_eur: float
    minimum_percent_savings: float
    maximum_percent_savings: float
    conservative_label: str
    optimistic_label: str
    rationale: str
    direct_breakdown: List[CostImpactBreakdown] = field(default_factory=list)
    linked_breakdown: List[CostImpactBreakdown] = field(default_factory=list)


@dataclass
class Recommendation:
    kind: str
    priority: int
    title: str
    summary: str
    impact: str
    actions: List[str]
    source: str
    feature_insights: List[FeatureInsight] = field(default_factory=list)
    cost_impact: Optional[CostImpactRange] = None


@dataclass
class AnalysisResult:
    file_path: str
    process_data: PartProcessData
    rules: List[RuleResult]
    summary: AnalysisSummary
    recommendations: List[Recommendation]
