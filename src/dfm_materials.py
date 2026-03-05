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


MATERIAL_OPTIONS: List[MaterialSpec] = [
    MaterialSpec(
        key="304_stainless_steel",
        label="304 stainless steel",
        density_kg_per_m3=7930.0,
        machinability_percent=43.0,
        machinability_source="https://www.machiningdoctor.com/mds/?matId=1750",
        baseline_billet_cost_eur_per_kg=3.8,
        baseline_billet_cost_source="https://www.jingangsteels.com/industry-news/304-stainless-steel-bar-price.html",
    ),
    MaterialSpec(
        key="6061_aluminium",
        label="6061 aluminium",
        density_kg_per_m3=2700.0,
        machinability_percent=270.0,
        machinability_source="https://www.machiningdoctor.com/mds/?matId=3850",
        baseline_billet_cost_eur_per_kg=3.0,
        baseline_billet_cost_source="https://luokaiweialuminum.com/2025/08/20/6061-aluminum-plate-price-2025/",
    ),
    MaterialSpec(
        key="1080_steel",
        label="1080 steel",
        density_kg_per_m3=7850.0,
        machinability_percent=48.0,
        machinability_source="https://www.machiningdoctor.com/mds/?matId=200",
        baseline_billet_cost_eur_per_kg=2.0,
        baseline_billet_cost_source="https://www.steelworld.co.in/high-carbon-c80-steel-sheet-10366004.html",
    ),
    MaterialSpec(
        key="grade_5_titanium",
        label="Grade 5 titanium",
        density_kg_per_m3=4430.0,
        machinability_percent=20.0,
        machinability_source="https://www.machiningdoctor.com/mds/?matId=6670",
        baseline_billet_cost_eur_per_kg=55.0,
        baseline_billet_cost_source="https://www.tiworker.com/products/gr5-eli-bar-titanium-price",
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
