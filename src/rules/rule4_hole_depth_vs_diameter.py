from __future__ import annotations

from typing import List, Optional, Tuple

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.GeomAbs import GeomAbs_Cylinder
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_IN
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape

from dfm_geometry import collect_faces
from dfm_models import Config, RuleResult


def cylinder_face_depth_and_diameter(face: TopoDS_Face) -> Optional[Tuple[float, float]]:
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Cylinder:
        return None
    radius = surf.Cylinder().Radius()
    u1, u2 = surf.FirstUParameter(), surf.LastUParameter()
    v1, v2 = surf.FirstVParameter(), surf.LastVParameter()
    depth = abs(v2 - v1)
    diameter = radius * 2.0
    if diameter <= precision.Confusion():
        return None
    return depth, diameter


def evaluate_hole_depth_vs_diameter(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    faces = collect_faces(shape)
    ratios: List[float] = []

    for face in faces:
        cyl = cylinder_face_depth_and_diameter(face)
        if cyl is None:
            continue
        depth, diameter = cyl
        surf = BRepAdaptor_Surface(face)
        center = surf.Value(
            (surf.FirstUParameter() + surf.LastUParameter()) * 0.5,
            (surf.FirstVParameter() + surf.LastVParameter()) * 0.5,
        )
        classifier = BRepClass3d_SolidClassifier(shape, center, precision.Confusion())
        if classifier.State() == TopAbs_IN:
            ratios.append(depth / diameter)

    if not ratios:
        return RuleResult(
            name="Rule 4 — Hole Depth vs Diameter",
            passed=True,
            summary="PASS",
            details="No cylindrical internal faces identified as holes.",
            detected_features=0,
            passed_features=0,
            failed_features=0,
        )

    worst = max(ratios)
    pass_count = sum(1 for ratio in ratios if ratio <= cfg.max_hole_depth_to_diameter)
    fail_count = len(ratios) - pass_count
    passed = fail_count == 0
    return RuleResult(
        name="Rule 4 — Hole Depth vs Diameter",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Worst detected hole depth/diameter ratio is {worst:.2f}; "
            f"maximum allowed is {cfg.max_hole_depth_to_diameter:.2f}."
        ),
        detected_features=len(ratios),
        passed_features=pass_count,
        failed_features=fail_count,
    )
