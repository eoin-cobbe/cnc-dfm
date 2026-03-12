from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_IN
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods
from OCC.Core.gp import gp_Dir, gp_Pnt

from dfm_feature_descriptions import feature_id, format_mm, nearest_axis_side, point3d
from dfm_geometry import (
    collect_faces,
    face_area,
    faces_for_edge,
    face_midpoint_and_normal,
    get_edge_face_map,
    is_internal_face,
    shape_bounds,
    shape_bbox,
    shape_centroid,
    signed_distance_between_planes,
)
from dfm_models import Config, FeatureInsight, RuleResult
from dfm_preview import export_feature_overlay_stl
from dfm_scoring import rule_multiplier_from_threshold

MIN_AXIS_FACE_AREA_FRACTION = 0.05


def _face_bbox(face: TopoDS_Face) -> Tuple[float, float, float, float, float, float]:
    box = Bnd_Box()
    brepbndlib.Add(face, box)
    return box.Get()


def _overlap_interval(a_min: float, a_max: float, b_min: float, b_max: float, tol: float = 0.05) -> Optional[Tuple[float, float]]:
    lo = max(a_min, b_min)
    hi = min(a_max, b_max)
    if hi < lo - tol:
        return None
    if hi < lo:
        # Small numeric mismatch; collapse to a single probe coordinate.
        mid = (lo + hi) * 0.5
        return mid, mid
    return lo, hi


def _wall_probe_point(
    face_i: TopoDS_Face, face_j: TopoDS_Face, normal: gp_Dir, point_i: gp_Pnt, point_j: gp_Pnt
) -> Optional[gp_Pnt]:
    xi1, yi1, zi1, xa1, ya1, za1 = _face_bbox(face_i)
    xi2, yi2, zi2, xa2, ya2, za2 = _face_bbox(face_j)
    nx, ny, nz = abs(normal.X()), abs(normal.Y()), abs(normal.Z())

    if nx >= ny and nx >= nz:
        oy = _overlap_interval(yi1, ya1, yi2, ya2)
        oz = _overlap_interval(zi1, za1, zi2, za2)
        if oy is None or oz is None:
            return None
        x = (point_i.X() + point_j.X()) * 0.5
        y = (oy[0] + oy[1]) * 0.5
        z = (oz[0] + oz[1]) * 0.5
        return gp_Pnt(x, y, z)
    if ny >= nx and ny >= nz:
        ox = _overlap_interval(xi1, xa1, xi2, xa2)
        oz = _overlap_interval(zi1, za1, zi2, za2)
        if ox is None or oz is None:
            return None
        x = (ox[0] + ox[1]) * 0.5
        y = (point_i.Y() + point_j.Y()) * 0.5
        z = (oz[0] + oz[1]) * 0.5
        return gp_Pnt(x, y, z)
    ox = _overlap_interval(xi1, xa1, xi2, xa2)
    oy = _overlap_interval(yi1, ya1, yi2, ya2)
    if ox is None or oy is None:
        return None
    x = (ox[0] + ox[1]) * 0.5
    y = (oy[0] + oy[1]) * 0.5
    z = (point_i.Z() + point_j.Z()) * 0.5
    return gp_Pnt(x, y, z)


def _wall_overlap_spans(face_i: TopoDS_Face, face_j: TopoDS_Face, normal: gp_Dir) -> Optional[Tuple[float, float]]:
    xi1, yi1, zi1, xa1, ya1, za1 = _face_bbox(face_i)
    xi2, yi2, zi2, xa2, ya2, za2 = _face_bbox(face_j)
    nx, ny, nz = abs(normal.X()), abs(normal.Y()), abs(normal.Z())

    if nx >= ny and nx >= nz:
        oy = _overlap_interval(yi1, ya1, yi2, ya2)
        oz = _overlap_interval(zi1, za1, zi2, za2)
        if oy is None or oz is None:
            return None
        return max(0.0, oy[1] - oy[0]), max(0.0, oz[1] - oz[0])
    if ny >= nx and ny >= nz:
        ox = _overlap_interval(xi1, xa1, xi2, xa2)
        oz = _overlap_interval(zi1, za1, zi2, za2)
        if ox is None or oz is None:
            return None
        return max(0.0, ox[1] - ox[0]), max(0.0, oz[1] - oz[0])
    ox = _overlap_interval(xi1, xa1, xi2, xa2)
    oy = _overlap_interval(yi1, ya1, yi2, ya2)
    if ox is None or oy is None:
        return None
    return max(0.0, ox[1] - ox[0]), max(0.0, oy[1] - oy[0])


def _shared_adjacent_faces(
    face_i: TopoDS_Face,
    face_j: TopoDS_Face,
    edge_face_map,
) -> List[TopoDS_Face]:
    adjacent_i: List[TopoDS_Face] = []
    exp_i = TopExp_Explorer(face_i, TopAbs_EDGE)
    while exp_i.More():
        edge = topods.Edge(exp_i.Current())
        for neighbor in faces_for_edge(edge_face_map, edge):
            if neighbor.IsSame(face_i) or neighbor.IsSame(face_j):
                continue
            if all(not existing.IsSame(neighbor) for existing in adjacent_i):
                adjacent_i.append(neighbor)
        exp_i.Next()

    shared: List[TopoDS_Face] = []
    exp_j = TopExp_Explorer(face_j, TopAbs_EDGE)
    while exp_j.More():
        edge = topods.Edge(exp_j.Current())
        for neighbor in faces_for_edge(edge_face_map, edge):
            if neighbor.IsSame(face_i) or neighbor.IsSame(face_j):
                continue
            if any(existing.IsSame(neighbor) for existing in adjacent_i) and all(
                not shared_face.IsSame(neighbor) for shared_face in shared
            ):
                shared.append(neighbor)
        exp_j.Next()
    return shared


def _top_cap_face_for_wall_pair(
    face_i: TopoDS_Face,
    face_j: TopoDS_Face,
    edge_face_map,
    thickness: float,
) -> Optional[TopoDS_Face]:
    candidates = _shared_adjacent_faces(face_i, face_j, edge_face_map)
    best_face: Optional[TopoDS_Face] = None
    best_score: Optional[Tuple[float, float, float]] = None
    for candidate in candidates:
        surf = BRepAdaptor_Surface(candidate)
        if surf.GetType() != GeomAbs_Plane:
            continue
        data = face_midpoint_and_normal(candidate)
        if data is None:
            continue
        point, _normal = data
        xmin, ymin, zmin, xmax, ymax, zmax = _face_bbox(candidate)
        spans = sorted(
            [
                max(0.0, xmax - xmin),
                max(0.0, ymax - ymin),
                max(0.0, zmax - zmin),
            ]
        )
        min_span = spans[0]
        span_error = abs(min_span - thickness)
        area = face_area(candidate)
        score = (-span_error, area, point.Z())
        if best_score is None or score > best_score:
            best_face = candidate
            best_score = score
    return best_face


def _opposing_planar_wall_features_by_axis(
    shape: TopoDS_Shape, max_angle_deg: float = 10.0
) -> Dict[str, List[dict]]:
    faces = collect_faces(shape)
    edge_face_map = get_edge_face_map(shape)
    centroid = shape_centroid(shape)
    dx, dy, dz = shape_bbox(shape)
    projected_axis_area = {
        "X": max(dy * dz, precision.Confusion()),
        "Y": max(dx * dz, precision.Confusion()),
        "Z": max(dx * dy, precision.Confusion()),
    }
    planar: List[Tuple[TopoDS_Face, gp_Pnt, gp_Dir, bool, float]] = []
    for face in faces:
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() != GeomAbs_Plane:
            continue
        data = face_midpoint_and_normal(face)
        if data is None:
            continue
        point, normal = data
        planar.append((face, point, normal, is_internal_face(face, centroid), face_area(face)))

    features_by_axis: Dict[str, List[dict]] = {"X": [], "Y": [], "Z": []}
    min_axis_dot = math.cos(math.radians(max_angle_deg))
    axis_dirs = [
        ("X", gp_Dir(1.0, 0.0, 0.0)),
        ("Y", gp_Dir(0.0, 1.0, 0.0)),
        ("Z", gp_Dir(0.0, 0.0, 1.0)),
    ]
    for axis_name, axis in axis_dirs:
        min_face_area = projected_axis_area[axis_name] * MIN_AXIS_FACE_AREA_FRACTION
        aligned = []
        for row in planar:
            _f, _p, n, _is_internal, area = row
            if area < min_face_area:
                continue
            if abs(n.XYZ().Dot(axis.XYZ())) >= min_axis_dot:
                aligned.append(row)

        for i in range(len(aligned)):
            face_i, point_i, normal_i, internal_i, _area_i = aligned[i]
            for j in range(i + 1, len(aligned)):
                face_j, point_j, normal_j, internal_j, _area_j = aligned[j]
                if internal_i == internal_j:
                    continue
                dot = normal_i.XYZ().Dot(normal_j.XYZ())
                if dot > -min_axis_dot:
                    continue

                dist = signed_distance_between_planes(face_i, face_j, normal_i)
                if dist is None:
                    continue
                thickness = abs(dist)
                if thickness <= precision.Confusion():
                    continue
                probe = _wall_probe_point(face_i, face_j, normal_i, point_i, point_j)
                if probe is None:
                    continue

                # Keep only pairs with solid material at the overlap-region midpoint.
                classifier = BRepClass3d_SolidClassifier(shape, probe, precision.Confusion())
                if classifier.State() != TopAbs_IN:
                    continue
                spans = _wall_overlap_spans(face_i, face_j, normal_i)
                span_a, span_b = spans if spans is not None else (0.0, 0.0)
                features_by_axis[axis_name].append(
                    {
                        "thickness": thickness,
                        "probe": probe,
                        "span_a": span_a,
                        "span_b": span_b,
                        "face_i": face_i,
                        "face_j": face_j,
                        "top_face": _top_cap_face_for_wall_pair(face_i, face_j, edge_face_map, thickness),
                    }
                )

    return features_by_axis


def evaluate_thin_walls(shape: TopoDS_Shape, cfg: Config, step_file: str | None = None) -> RuleResult:
    wall_features_by_axis = _opposing_planar_wall_features_by_axis(shape)
    bounds = shape_bounds(shape)
    thicknesses = [
        float(feature["thickness"])
        for axis in ("X", "Y", "Z")
        for feature in wall_features_by_axis[axis]
    ]
    axis_breakdown: Dict[str, Tuple[int, int, int]] = {}
    feature_insight_rows: List[Tuple[float, FeatureInsight]] = []
    for axis in ("X", "Y", "Z"):
        axis_vals = wall_features_by_axis[axis]
        axis_detected = len(axis_vals)
        axis_pass = sum(1 for feature in axis_vals if float(feature["thickness"]) >= cfg.min_wall_thickness_mm)
        axis_fail = axis_detected - axis_pass
        axis_breakdown[axis] = (axis_detected, axis_pass, axis_fail)
        for feature in axis_vals:
            thickness = float(feature["thickness"])
            if thickness >= cfg.min_wall_thickness_mm:
                continue
            side = nearest_axis_side(feature["probe"], bounds, axis)
            span_major = max(float(feature["span_a"]), float(feature["span_b"]))
            span_minor = min(float(feature["span_a"]), float(feature["span_b"]))
            overlay_faces = [feature["top_face"]] if feature.get("top_face") is not None else [feature["face_i"], feature["face_j"]]
            overlay_mesh_paths = (
                export_feature_overlay_stl(
                    step_file,
                    feature_id(
                        "rule3-overlay-v2",
                        axis,
                        round(feature["probe"].X(), 3),
                        round(feature["probe"].Y(), 3),
                        round(feature["probe"].Z(), 3),
                        round(thickness, 3),
                    ),
                    overlay_faces,
                )
                if step_file is not None
                else []
            )
            feature_insight_rows.append(
                (
                    thickness,
                    FeatureInsight(
                        id=feature_id(
                            "rule3",
                            axis,
                            round(feature["probe"].X(), 3),
                            round(feature["probe"].Y(), 3),
                            round(feature["probe"].Z(), 3),
                            round(thickness, 3),
                        ),
                        summary=(
                            f"{format_mm(thickness)} wall on the {side} side spanning about {format_mm(span_major)} x "
                            f"{format_mm(span_minor)}."
                        ),
                        highlight_kind="wall_pair",
                        axis=axis,
                        measured_value=thickness,
                        target_value=cfg.min_wall_thickness_mm,
                        units="mm",
                        anchor=point3d(feature["probe"]),
                        overlay_mesh_paths=overlay_mesh_paths,
                    ),
                )
            )

    if not thicknesses:
        return RuleResult(
            name="Rule 3 — Wall Thickness",
            passed=True,
            summary="PASS",
            details="No opposing planar wall pairs with solid material between them were detected.",
            detected_features=0,
            passed_features=0,
            failed_features=0,
            axis_breakdown=axis_breakdown,
            metric_label="Wall (mm)",
            average_detected=0.0,
            threshold=cfg.min_wall_thickness_mm,
            threshold_kind="min",
            rule_multiplier=1.0,
            feature_insights=[],
        )

    thinnest = min(thicknesses)
    avg_thickness = sum(thicknesses) / len(thicknesses)
    rule_mult = rule_multiplier_from_threshold(
        average_detected=avg_thickness,
        threshold=cfg.min_wall_thickness_mm,
        threshold_kind="min",
    )
    pass_count = sum(1 for t in thicknesses if t >= cfg.min_wall_thickness_mm)
    fail_count = len(thicknesses) - pass_count
    passed = fail_count == 0
    return RuleResult(
        name="Rule 3 — Thin Walls",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Minimum detected wall thickness is {thinnest:.3f} mm; "
            f"required minimum is {cfg.min_wall_thickness_mm:.3f} mm."
        ),
        detected_features=len(thicknesses),
        passed_features=pass_count,
        failed_features=fail_count,
        axis_breakdown=axis_breakdown,
        minimum_detected=thinnest,
        required_minimum=cfg.min_wall_thickness_mm,
        metric_label="Wall (mm)",
        average_detected=avg_thickness,
        threshold=cfg.min_wall_thickness_mm,
        threshold_kind="min",
        rule_multiplier=rule_mult,
        feature_insights=[insight for _score, insight in sorted(feature_insight_rows, key=lambda row: row[0])],
    )
