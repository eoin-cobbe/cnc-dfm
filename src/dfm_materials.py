from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MaterialSpec:
    key: str
    label: str
    density_kg_per_m3: float
    machinability_percent: float
    machinability_source: str
    baseline_billet_cost_eur_per_kg: float
    baseline_billet_cost_source: str
    baseline_fixed_stock_cost_eur: float
    baseline_fixed_stock_cost_source: str


MATERIAL_OPTIONS: List[MaterialSpec] = [
    MaterialSpec(
        key="304_stainless_steel",
        label="304 stainless steel",
        density_kg_per_m3=7930.0,
        machinability_percent=125.4,
        machinability_source="xometry delta-quote calibration (2026-03-05): (421-210)/(209-111)=2.153x vs 6061",
        baseline_billet_cost_eur_per_kg=11.49,
        baseline_billet_cost_source="xometry no-pocket two-point fit (2026-03-05)",
        baseline_fixed_stock_cost_eur=87.0,
        baseline_fixed_stock_cost_source="xometry no-pocket two-point fit (2026-03-05)",
    ),
    MaterialSpec(
        key="6061_aluminium",
        label="6061 aluminium",
        density_kg_per_m3=2700.0,
        machinability_percent=270.0,
        machinability_source="https://www.machiningdoctor.com/mds/?matId=3850",
        baseline_billet_cost_eur_per_kg=16.46,
        baseline_billet_cost_source="xometry no-pocket two-point fit (2026-03-05)",
        baseline_fixed_stock_cost_eur=51.0,
        baseline_fixed_stock_cost_source="xometry no-pocket two-point fit (2026-03-05)",
    ),
    MaterialSpec(
        key="1080_steel",
        label="1080 steel",
        density_kg_per_m3=7850.0,
        machinability_percent=224.2,
        machinability_source="xometry delta-quote calibration (2026-03-05): (244-126)/(209-111)=1.204x vs 6061",
        baseline_billet_cost_eur_per_kg=6.65,
        baseline_billet_cost_source="xometry no-pocket two-point fit (2026-03-05)",
        baseline_fixed_stock_cost_eur=55.5,
        baseline_fixed_stock_cost_source="xometry no-pocket two-point fit (2026-03-05)",
    ),
    MaterialSpec(
        key="grade_5_titanium",
        label="Grade 5 titanium",
        density_kg_per_m3=4430.0,
        machinability_percent=65.5,
        machinability_source="xometry delta-quote calibration (2026-03-05): (704-300)/(209-111)=4.122x vs 6061",
        baseline_billet_cost_eur_per_kg=23.33,
        baseline_billet_cost_source="xometry no-pocket two-point fit (2026-03-05)",
        baseline_fixed_stock_cost_eur=160.5,
        baseline_fixed_stock_cost_source="xometry no-pocket two-point fit (2026-03-05)",
    ),
]

MATERIALS_BY_KEY: Dict[str, MaterialSpec] = {mat.key: mat for mat in MATERIAL_OPTIONS}
MATERIALS_BY_LABEL: Dict[str, MaterialSpec] = {mat.label.lower(): mat for mat in MATERIAL_OPTIONS}

DEFAULT_MATERIAL_KEY = MATERIAL_OPTIONS[0].key


def material_keys() -> List[str]:
    return [mat.key for mat in MATERIAL_OPTIONS]


def get_material(key_or_label: str) -> MaterialSpec:
    lowered = key_or_label.strip().lower()
    if lowered in MATERIALS_BY_KEY:
        return MATERIALS_BY_KEY[lowered]
    if lowered in MATERIALS_BY_LABEL:
        return MATERIALS_BY_LABEL[lowered]
    raise KeyError(f"Unknown material: {key_or_label}")
