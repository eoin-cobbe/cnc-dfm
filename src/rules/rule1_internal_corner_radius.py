from __future__ import annotations

import math
from typing import Dict, List, Tuple

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods
from OCC.Core.gp import gp_Dir

from dfm_geometry import (
    face_midpoint_and_normal,
    faces_for_edge,
    get_edge_face_map,
    is_parallel,
    offset_is_outside,
)
from dfm_models import Config, RuleResult


def detect_internal_corner_radii(shape: TopoDS_Shape) -> Dict[str, List[float]]:
    edge_face_map = get_edge_face_map(shape)
    axis_specs: List[Tuple[str, gp_Dir]] = [
        ("X", gp_Dir(1.0, 0.0, 0.0)),
        ("Y", gp_Dir(0.0, 1.0, 0.0)),
        ("Z", gp_Dir(0.0, 0.0, 1.0)),
    ]
    radii_by_axis: Dict[str, List[float]] = {}

    def is_concave_internal_cylinder(face: TopoDS_Face) -> bool:
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

    for axis_name, opening_axis in axis_specs:
        radii: List[float] = []
        face_exp = TopExp_Explorer(shape, TopAbs_FACE)
        while face_exp.More():
            face = topods.Face(face_exp.Current())
            surf = BRepAdaptor_Surface(face)
            if surf.GetType() != GeomAbs_Cylinder:
                face_exp.Next()
                continue

            cyl_axis = surf.Cylinder().Axis().Direction()
            if not is_parallel(cyl_axis, opening_axis, 20.0):
                face_exp.Next()
                continue

            if not is_concave_internal_cylinder(face):
                face_exp.Next()
                continue

            planar_normals: List[gp_Dir] = []
            edge_exp = TopExp_Explorer(face, TopAbs_EDGE)
            while edge_exp.More():
                edge = topods.Edge(edge_exp.Current())
                for nbr in faces_for_edge(edge_face_map, edge):
                    if nbr.IsSame(face):
                        continue
                    ns = BRepAdaptor_Surface(nbr)
                    if ns.GetType() != GeomAbs_Plane:
                        continue
                    data = face_midpoint_and_normal(nbr)
                    if data is None:
                        continue
                    _pt, n = data
                    if all(abs(n.XYZ().Dot(existing.XYZ())) < math.cos(math.radians(10.0)) for existing in planar_normals):
                        planar_normals.append(n)
                edge_exp.Next()

            if len(planar_normals) < 2:
                face_exp.Next()
                continue

            radii.append(surf.Cylinder().Radius())
            face_exp.Next()

        radii_by_axis[axis_name] = radii

    return radii_by_axis


def detect_internal_corner_features(shape: TopoDS_Shape) -> Dict[str, List[dict]]:
    edge_face_map = get_edge_face_map(shape)
    axis_specs: List[Tuple[str, gp_Dir]] = [
        ("X", gp_Dir(1.0, 0.0, 0.0)),
        ("Y", gp_Dir(0.0, 1.0, 0.0)),
        ("Z", gp_Dir(0.0, 0.0, 1.0)),
    ]
    features_by_axis: Dict[str, List[dict]] = {}

    def is_concave_internal_cylinder(face: TopoDS_Face) -> bool:
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

    for axis_name, opening_axis in axis_specs:
        features: List[dict] = []
        seen = set()
        face_exp = TopExp_Explorer(shape, TopAbs_FACE)
        while face_exp.More():
            face = topods.Face(face_exp.Current())
            surf = BRepAdaptor_Surface(face)
            if surf.GetType() != GeomAbs_Cylinder:
                face_exp.Next()
                continue

            cyl_axis = surf.Cylinder().Axis().Direction()
            if not is_parallel(cyl_axis, opening_axis, 20.0):
                face_exp.Next()
                continue

            if not is_concave_internal_cylinder(face):
                face_exp.Next()
                continue

            planar_normals: List[gp_Dir] = []
            wall_faces: List[TopoDS_Face] = []
            edge_exp = TopExp_Explorer(face, TopAbs_EDGE)
            while edge_exp.More():
                edge = topods.Edge(edge_exp.Current())
                for nbr in faces_for_edge(edge_face_map, edge):
                    if nbr.IsSame(face):
                        continue
                    ns = BRepAdaptor_Surface(nbr)
                    if ns.GetType() != GeomAbs_Plane:
                        continue
                    data = face_midpoint_and_normal(nbr)
                    if data is None:
                        continue
                    _pt, n = data
                    if all(abs(n.XYZ().Dot(existing.XYZ())) < math.cos(math.radians(10.0)) for existing in planar_normals):
                        planar_normals.append(n)
                    if all(not existing.IsSame(nbr) for existing in wall_faces):
                        wall_faces.append(nbr)
                edge_exp.Next()

            if len(planar_normals) < 2:
                face_exp.Next()
                continue

            u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
            v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
            c_mid = surf.Value(u, v)
            radius = surf.Cylinder().Radius()
            depth_along_axis = c_mid.X() * opening_axis.X() + c_mid.Y() * opening_axis.Y() + c_mid.Z() * opening_axis.Z()
            cylindrical_depth = abs(surf.LastVParameter() - surf.FirstVParameter())
            key = (
                round(c_mid.X(), 2),
                round(c_mid.Y(), 2),
                round(c_mid.Z(), 2),
                round(radius, 4),
                round(cylindrical_depth, 4),
            )
            if key in seen:
                face_exp.Next()
                continue
            seen.add(key)
            features.append(
                {
                    "radius": radius,
                    "depth_along_axis": depth_along_axis,
                    "cylindrical_depth": cylindrical_depth,
                    "midpoint": c_mid,
                    "wall_faces": wall_faces,
                }
            )
            face_exp.Next()

        features_by_axis[axis_name] = features

    return features_by_axis


def evaluate_internal_corner_radius(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    radii_by_axis = detect_internal_corner_radii(shape)
    feature_radii: List[float] = []
    axis_breakdown: Dict[str, Tuple[int, int, int]] = {
        "X": (0, 0, 0),
        "Y": (0, 0, 0),
        "Z": (0, 0, 0),
    }

    for axis_name, axis_radii in radii_by_axis.items():
        axis_detected = len(axis_radii)
        axis_pass = sum(1 for r in axis_radii if r >= cfg.min_internal_corner_radius_mm)
        axis_fail = axis_detected - axis_pass

        feature_radii.extend(axis_radii)
        axis_breakdown[axis_name] = (axis_detected, axis_pass, axis_fail)

    if not feature_radii:
        return RuleResult(
            name="Rule 1 — Internal Corner Radius Too Small",
            passed=True,
            summary="PASS",
            details="No exposed internal corner features detected for Rule 1.",
            detected_features=0,
            passed_features=0,
            failed_features=0,
            axis_breakdown=axis_breakdown,
            required_minimum=cfg.min_internal_corner_radius_mm,
        )

    min_radius = min(feature_radii)
    pass_count = sum(1 for r in feature_radii if r >= cfg.min_internal_corner_radius_mm)
    fail_count = len(feature_radii) - pass_count
    passed = fail_count == 0
    return RuleResult(
        name="Rule 1 — Internal Corner Radius Too Small",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            "Internal corner radii evaluated."
        ),
        detected_features=len(feature_radii),
        passed_features=pass_count,
        failed_features=fail_count,
        axis_breakdown=axis_breakdown,
        minimum_detected=min_radius,
        required_minimum=cfg.min_internal_corner_radius_mm,
    )
