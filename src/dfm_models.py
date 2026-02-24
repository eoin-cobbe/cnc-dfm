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


@dataclass
class Config:
    min_internal_corner_radius_mm: float = 6.0
    max_pocket_depth_ratio: float = 4.0
    min_wall_thickness_mm: float = 1.0
    max_hole_depth_to_diameter: float = 6.0
    max_setups: int = 2
    normal_similarity_deg: float = 12.0
