from __future__ import annotations

import math
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods
from OCC.Core.gp import gp_Dir, gp_Pnt

from dfm_geometry import (
    collect_faces,
    face_midpoint_and_normal,
    faces_for_edge,
    get_edge_face_map,
    offset_is_outside,
    shape_bbox,
)
from dfm_models import Config, RuleResult
from .rule4_hole_depth_vs_diameter import _has_hole_opening_or_cap_plane, _is_concave_internal_cylinder


AXIS_DIRS: Dict[str, gp_Dir] = {
    "X": gp_Dir(1.0, 0.0, 0.0),
    "Y": gp_Dir(0.0, 1.0, 0.0),
    "Z": gp_Dir(0.0, 0.0, 1.0),
}
ALL_SETUP_KEYS = tuple(f"{axis}{side}" for axis in ("X", "Y", "Z") for side in ("+", "-"))


def _dot(a: gp_Dir, b: gp_Dir) -> float:
    return a.X() * b.X() + a.Y() * b.Y() + a.Z() * b.Z()


def _dominant_axis_name(normal: gp_Dir, bucket_deg: float) -> Optional[str]:
    min_axis_dot = math.cos(math.radians(bucket_deg))
    components = {
        "X": abs(normal.X()),
        "Y": abs(normal.Y()),
        "Z": abs(normal.Z()),
    }
    axis = max(components, key=components.get)
    if components[axis] < min_axis_dot:
        return None
    return axis


def _setup_key(axis_name: str, side: str) -> str:
    return f"{axis_name}{side}"


def _move(point: gp_Pnt, direction: gp_Dir, distance: float) -> gp_Pnt:
    return gp_Pnt(
        point.X() + direction.X() * distance,
        point.Y() + direction.Y() * distance,
        point.Z() + direction.Z() * distance,
    )


def _feature_key(face: TopoDS_Face) -> Tuple[float, float, float, float, float]:
    surf = BRepAdaptor_Surface(face)
    u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
    v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
    c_mid = surf.Value(u, v)
    return (
        round(c_mid.X(), 2),
        round(c_mid.Y(), 2),
        round(c_mid.Z(), 2),
        round(surf.Cylinder().Radius(), 4),
        round(abs(surf.LastVParameter() - surf.FirstVParameter()), 4),
    )


def _cylinder_midpoint(face: TopoDS_Face) -> gp_Pnt:
    surf = BRepAdaptor_Surface(face)
    u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
    v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
    return surf.Value(u, v)


def _cylinder_radial_direction(face: TopoDS_Face) -> Optional[gp_Dir]:
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Cylinder:
        return None
    u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
    v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
    p_mid = surf.Value(u, v)

    axis = surf.Cylinder().Axis()
    loc = axis.Location()
    direction = axis.Direction()

    w = p_mid.XYZ().Subtracted(loc.XYZ())
    along = w.Dot(direction.XYZ())
    foot_xyz = loc.XYZ().Added(direction.XYZ().Multiplied(along))
    radial_xyz = p_mid.XYZ().Subtracted(foot_xyz)
    if radial_xyz.Modulus() <= precision.Confusion():
        return None
    return gp_Dir(radial_xyz)


def _void_probe_point(shape: TopoDS_Shape, face: TopoDS_Face, probe_mm: float = 0.3) -> Optional[gp_Pnt]:
    mid = _cylinder_midpoint(face)
    radial = _cylinder_radial_direction(face)
    if radial is None:
        return None

    inward = gp_Dir(-radial.X(), -radial.Y(), -radial.Z())
    if offset_is_outside(shape, mid, inward, distance=probe_mm):
        return _move(mid, inward, probe_mm)
    if offset_is_outside(shape, mid, radial, distance=probe_mm):
        return _move(mid, radial, probe_mm)
    return None


def _approach_direction(axis_name: str, side: str) -> gp_Dir:
    base = AXIS_DIRS[axis_name]
    if side == "+":
        return base
    return gp_Dir(-base.X(), -base.Y(), -base.Z())


def _is_clear_approach(shape: TopoDS_Shape, probe_point: gp_Pnt, approach: gp_Dir, max_travel: float) -> bool:
    step = 0.5
    distance = step
    while distance <= max_travel:
        if not offset_is_outside(shape, probe_point, approach, distance=distance):
            return False
        distance += step
    return True


def _adjacent_planar_normals(
    face: TopoDS_Face,
    edge_face_map,
    cfg: Config,
) -> Tuple[List[gp_Dir], List[Tuple[str, str]]]:
    wall_normals: List[gp_Dir] = []
    cap_setups: List[Tuple[str, str]] = []

    edge_exp = TopExp_Explorer(face, TopAbs_EDGE)
    while edge_exp.More():
        edge = topods.Edge(edge_exp.Current())
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
            axis_name = _dominant_axis_name(normal, cfg.normal_similarity_deg)
            if axis_name is None:
                continue
            sign = "+" if _dot(normal, AXIS_DIRS[axis_name]) >= 0.0 else "-"
            cap_setups.append((axis_name, sign))
            if all(abs(_dot(normal, existing)) < math.cos(math.radians(10.0)) for existing in wall_normals):
                wall_normals.append(normal)
        edge_exp.Next()

    return wall_normals, cap_setups


def _feature_reachable_setups(shape: TopoDS_Shape, face: TopoDS_Face, cfg: Config) -> Set[str]:
    surf = BRepAdaptor_Surface(face)
    axis_name = _dominant_axis_name(surf.Cylinder().Axis().Direction(), cfg.normal_similarity_deg)
    if axis_name is None:
        return set()

    probe_point = _void_probe_point(shape, face)
    if probe_point is None:
        return set()

    bbox = shape_bbox(shape)
    max_travel = max(bbox) + math.sqrt(bbox[0] ** 2 + bbox[1] ** 2 + bbox[2] ** 2) + 2.0

    reachable: Set[str] = set()
    for side in ("+", "-"):
        if _is_clear_approach(shape, probe_point, _approach_direction(axis_name, side), max_travel):
            reachable.add(_setup_key(axis_name, side))
    return reachable


def _collect_feature_access_sets(shape: TopoDS_Shape, cfg: Config) -> List[Set[str]]:
    edge_face_map = get_edge_face_map(shape)
    features: List[Set[str]] = []
    seen: Set[Tuple[float, float, float, float, float]] = set()

    for face in collect_faces(shape):
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() != GeomAbs_Cylinder:
            continue

        key = _feature_key(face)
        if key in seen:
            continue

        is_hole = _is_concave_internal_cylinder(shape, face) and _has_hole_opening_or_cap_plane(edge_face_map, face)
        wall_normals, cap_setups = _adjacent_planar_normals(face, edge_face_map, cfg)
        axis_name = _dominant_axis_name(surf.Cylinder().Axis().Direction(), cfg.normal_similarity_deg)
        if axis_name is None:
            continue

        non_axis_walls = [
            normal
            for normal in wall_normals
            if _dominant_axis_name(normal, cfg.normal_similarity_deg) != axis_name
        ]
        is_radius = len(non_axis_walls) >= 2 and not is_hole
        if not is_hole and not is_radius:
            continue

        seen.add(key)
        reachable = _feature_reachable_setups(shape, face, cfg)
        if reachable:
            features.append(reachable)
            continue

        # Fallback if the access probe is inconclusive: preserve the feature on its
        # axis using the best local evidence we have rather than dropping it.
        fallback: Set[str] = set()
        for cap_axis, cap_side in cap_setups:
            if cap_axis == axis_name:
                fallback.add(_setup_key(cap_axis, cap_side))
        if not fallback:
            fallback.add(_setup_key(axis_name, "+"))
        features.append(fallback)

    return features


def _minimum_setup_cover(features: List[Set[str]]) -> Set[str]:
    if not features:
        return set()

    coverage: Dict[str, Set[int]] = {key: set() for key in ALL_SETUP_KEYS}
    for idx, reachable in enumerate(features):
        for key in reachable:
            coverage.setdefault(key, set()).add(idx)

    usable_keys = sorted(key for key, covered in coverage.items() if covered)
    target = set(range(len(features)))

    for size in range(1, len(usable_keys) + 1):
        for combo in combinations(usable_keys, size):
            covered: Set[int] = set()
            for key in combo:
                covered.update(coverage[key])
            if covered == target:
                return set(combo)

    return set(usable_keys)


def evaluate_multiple_setup_faces(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    feature_access_sets = _collect_feature_access_sets(shape, cfg)
    setup_keys = _minimum_setup_cover(feature_access_sets)
    setups = len(setup_keys)
    fail_count = max(setups - cfg.max_setups, 0)
    pass_count = setups - fail_count
    passed = fail_count == 0
    axis_breakdown = {
        axis_name: (
            sum(1 for key in setup_keys if key.startswith(axis_name)),
            sum(1 for key in setup_keys if key.startswith(axis_name)),
            0,
        )
        for axis_name in ("X", "Y", "Z")
    }
    setup_text = ", ".join(sorted(setup_keys)) if setup_keys else "none"
    return RuleResult(
        name="Rule 5 — Multiple Setup Faces",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Minimum required machining setup directions: {setup_text} ({setups} total) "
            f"to cover {len(feature_access_sets)} feature groups; maximum allowed is {cfg.max_setups}."
        ),
        detected_features=setups,
        passed_features=pass_count,
        failed_features=fail_count,
        axis_breakdown=axis_breakdown,
    )
