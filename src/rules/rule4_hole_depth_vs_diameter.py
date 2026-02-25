from __future__ import annotations

from typing import List, Optional, Set, Tuple

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods
from OCC.Core.gp import gp_Dir

from dfm_geometry import (
    collect_faces,
    face_midpoint_and_normal,
    faces_for_edge,
    get_edge_face_map,
    is_parallel,
    offset_is_outside,
)
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


def _is_concave_internal_cylinder(shape: TopoDS_Shape, face: TopoDS_Face) -> bool:
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Cylinder:
        return False
    u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
    v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
    p_mid = surf.Value(u, v)

    axis = surf.Cylinder().Axis()
    loc = axis.Location()
    d = axis.Direction()

    w = p_mid.XYZ().Subtracted(loc.XYZ())
    along = w.Dot(d.XYZ())
    foot_xyz = loc.XYZ().Added(d.XYZ().Multiplied(along))
    radial_xyz = p_mid.XYZ().Subtracted(foot_xyz)
    if radial_xyz.Modulus() <= precision.Confusion():
        return False
    radial = gp_Dir(radial_xyz)

    toward_out = offset_is_outside(
        shape,
        p_mid,
        gp_Dir(-radial.X(), -radial.Y(), -radial.Z()),
        distance=0.25,
    )
    away_out = offset_is_outside(shape, p_mid, radial, distance=0.25)
    return toward_out and not away_out


def _has_hole_opening_or_cap_plane(edge_face_map, face: TopoDS_Face) -> bool:
    # Hole-like cylindrical faces are typically bounded by at least one planar face
    # whose normal is parallel to the cylinder axis (entry face or blind-hole bottom).
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Cylinder:
        return False
    cyl_axis = surf.Cylinder().Axis().Direction()

    exp = TopExp_Explorer(face, TopAbs_EDGE)
    while exp.More():
        edge = topods.Edge(exp.Current())
        for nbr in faces_for_edge(edge_face_map, edge):
            if nbr.IsSame(face):
                continue
            nbr_surf = BRepAdaptor_Surface(nbr)
            if nbr_surf.GetType() != GeomAbs_Plane:
                continue
            data = face_midpoint_and_normal(nbr)
            if data is None:
                continue
            _pt, normal = data
            if is_parallel(normal, cyl_axis, 20.0):
                return True
        exp.Next()
    return False


def evaluate_hole_depth_vs_diameter(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    faces = collect_faces(shape)
    edge_face_map = get_edge_face_map(shape)
    ratios: List[float] = []
    seen: Set[Tuple[float, float, float, float, float]] = set()
    axis_ratios = {"X": [], "Y": [], "Z": []}

    for face in faces:
        cyl = cylinder_face_depth_and_diameter(face)
        if cyl is None:
            continue
        if not _is_concave_internal_cylinder(shape, face):
            continue
        if not _has_hole_opening_or_cap_plane(edge_face_map, face):
            continue
        depth, diameter = cyl
        surf = BRepAdaptor_Surface(face)
        u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
        v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
        c_mid = surf.Value(u, v)
        key = (
            round(c_mid.X(), 2),
            round(c_mid.Y(), 2),
            round(c_mid.Z(), 2),
            round(diameter, 4),
            round(depth, 4),
        )
        if key in seen:
            continue
        seen.add(key)
        ratio = depth / diameter
        ratios.append(ratio)
        cyl_axis = surf.Cylinder().Axis().Direction()
        axis_values = {
            "X": abs(cyl_axis.X()),
            "Y": abs(cyl_axis.Y()),
            "Z": abs(cyl_axis.Z()),
        }
        dominant_axis = max(axis_values, key=axis_values.get)
        axis_ratios[dominant_axis].append(ratio)

    axis_breakdown = {}
    for axis in ("X", "Y", "Z"):
        axis_vals = axis_ratios[axis]
        axis_detected = len(axis_vals)
        axis_pass = sum(1 for ratio in axis_vals if ratio <= cfg.max_hole_depth_to_diameter)
        axis_fail = axis_detected - axis_pass
        axis_breakdown[axis] = (axis_detected, axis_pass, axis_fail)

    if not ratios:
        return RuleResult(
            name="Rule 4 — Hole Depth vs Diameter",
            passed=True,
            summary="PASS",
            details="No cylindrical internal faces identified as holes.",
            detected_features=0,
            passed_features=0,
            failed_features=0,
            axis_breakdown=axis_breakdown,
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
        axis_breakdown=axis_breakdown,
    )
