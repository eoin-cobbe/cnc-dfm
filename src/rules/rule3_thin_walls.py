from __future__ import annotations

import math
from typing import List, Optional, Tuple

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_IN
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape
from OCC.Core.gp import gp_Dir, gp_Pnt

from dfm_geometry import (
    collect_faces,
    face_area,
    face_midpoint_and_normal,
    is_internal_face,
    shape_bbox,
    shape_centroid,
    signed_distance_between_planes,
)
from dfm_models import Config, RuleResult

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


def _opposing_planar_wall_thicknesses(shape: TopoDS_Shape, max_angle_deg: float = 10.0) -> List[float]:
    faces = collect_faces(shape)
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

    thicknesses: List[float] = []
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
                thicknesses.append(thickness)

    return thicknesses


def evaluate_thin_walls(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    thicknesses = _opposing_planar_wall_thicknesses(shape)
    if not thicknesses:
        return RuleResult(
            name="Rule 3 — Wall Thickness",
            passed=True,
            summary="PASS",
            details="No opposing planar wall pairs with solid material between them were detected.",
            detected_features=0,
            passed_features=0,
            failed_features=0,
        )

    thinnest = min(thicknesses)
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
        minimum_detected=thinnest,
        required_minimum=cfg.min_wall_thickness_mm,
    )
