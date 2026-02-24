from __future__ import annotations

from OCC.Core.TopoDS import TopoDS_Shape

from dfm_geometry import shape_bbox
from dfm_models import Config, RuleResult


def evaluate_thin_walls(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    dx, dy, dz = shape_bbox(shape)
    min_envelope = min(dx, dy, dz)
    passed = min_envelope >= cfg.min_wall_thickness_mm
    return RuleResult(
        name="Rule 3 — Thin Walls",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Minimum global envelope thickness is {min_envelope:.3f} mm; "
            f"required minimum wall thickness is {cfg.min_wall_thickness_mm:.3f} mm."
        ),
        detected_features=1,
        passed_features=1 if passed else 0,
        failed_features=0 if passed else 1,
    )
