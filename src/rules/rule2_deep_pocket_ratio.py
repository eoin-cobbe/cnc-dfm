from __future__ import annotations

from typing import Dict, List, Tuple

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer, topexp
from OCC.Core.TopoDS import TopoDS_Shape, topods
from OCC.Core.gp import gp_Dir, gp_Pnt

from dfm_geometry import (
    axis_depth,
    axis_perp_components,
    external_axis_openings,
    faces_for_edge,
    get_edge_face_map,
    is_internal_face,
    is_parallel,
    is_wall_face_for_axis,
    shape_centroid,
)
from dfm_models import Config, RuleResult


def _safe_dir_from_points(p_from: gp_Pnt, p_to: gp_Pnt):
    vec = p_to.XYZ().Subtracted(p_from.XYZ())
    mag = vec.Modulus()
    if mag <= precision.Confusion():
        return None
    return gp_Dir(vec)


def detect_internal_corner_layers(shape: TopoDS_Shape) -> Dict[str, List[dict]]:
    edge_face_map = get_edge_face_map(shape)
    centroid = shape_centroid(shape)
    axis_specs: List[Tuple[str, gp_Dir]] = [
        ("X", gp_Dir(1.0, 0.0, 0.0)),
        ("Y", gp_Dir(0.0, 1.0, 0.0)),
        ("Z", gp_Dir(0.0, 0.0, 1.0)),
    ]
    layers_by_axis: Dict[str, List[dict]] = {}

    for axis_name, opening_axis in axis_specs:
        rounded: List[Tuple[float, float, gp_Pnt]] = []
        rounded_seen = set()
        face_exp = TopExp_Explorer(shape, TopAbs_FACE)
        while face_exp.More():
            face = topods.Face(face_exp.Current())
            surf = BRepAdaptor_Surface(face)
            if surf.GetType() == GeomAbs_Cylinder:
                cyl_axis = surf.Cylinder().Axis().Direction()
                if is_parallel(cyl_axis, opening_axis, 20.0):
                    internal_wall_neighbors = 0
                    edge_exp = TopExp_Explorer(face, TopAbs_EDGE)
                    while edge_exp.More():
                        edge = topods.Edge(edge_exp.Current())
                        for nbr in faces_for_edge(edge_face_map, edge):
                            if nbr.IsSame(face):
                                continue
                            ns = BRepAdaptor_Surface(nbr)
                            if ns.GetType() != GeomAbs_Plane:
                                continue
                            if is_internal_face(nbr, centroid) and is_wall_face_for_axis(nbr, opening_axis):
                                internal_wall_neighbors += 1
                        edge_exp.Next()
                    if internal_wall_neighbors < 2:
                        face_exp.Next()
                        continue

                    u = (surf.FirstUParameter() + surf.LastUParameter()) * 0.5
                    v = (surf.FirstVParameter() + surf.LastVParameter()) * 0.5
                    c_mid = surf.Value(u, v)
                    d = axis_depth(c_mid, opening_axis)
                    r = surf.Cylinder().Radius()
                    key = (round(c_mid.X(), 1), round(c_mid.Y(), 1), round(c_mid.Z(), 1), round(r, 3))
                    if key not in rounded_seen:
                        rounded_seen.add(key)
                        rounded.append((d, r, c_mid))
            face_exp.Next()

        sharp: List[Tuple[float, gp_Pnt]] = []
        edge_exp = TopExp_Explorer(shape, TopAbs_EDGE)
        sharp_seen = set()
        while edge_exp.More():
            edge = topods.Edge(edge_exp.Current())
            curve = BRepAdaptor_Curve(edge)
            if curve.GetType() == GeomAbs_Circle:
                edge_exp.Next()
                continue

            faces = faces_for_edge(edge_face_map, edge)
            if len(faces) != 2:
                edge_exp.Next()
                continue
            f1, f2 = faces[0], faces[1]
            s1 = BRepAdaptor_Surface(f1)
            s2 = BRepAdaptor_Surface(f2)
            if s1.GetType() != GeomAbs_Plane or s2.GetType() != GeomAbs_Plane:
                edge_exp.Next()
                continue
            if not (is_internal_face(f1, centroid) and is_internal_face(f2, centroid)):
                edge_exp.Next()
                continue
            if not (is_wall_face_for_axis(f1, opening_axis) and is_wall_face_for_axis(f2, opening_axis)):
                edge_exp.Next()
                continue

            v_first = topods.Vertex(topexp.FirstVertex(edge))
            v_last = topods.Vertex(topexp.LastVertex(edge))
            p_first = BRep_Tool.Pnt(v_first)
            p_last = BRep_Tool.Pnt(v_last)
            edge_dir = _safe_dir_from_points(p_first, p_last)
            if edge_dir is None or not is_parallel(edge_dir, opening_axis, 20.0):
                edge_exp.Next()
                continue

            p0 = curve.FirstParameter()
            p1 = curve.LastParameter()
            p_mid = curve.Value((p0 + p1) * 0.5)
            key = (round(p_mid.X(), 2), round(p_mid.Y(), 2), round(p_mid.Z(), 2))
            if key in sharp_seen:
                edge_exp.Next()
                continue
            sharp_seen.add(key)
            sharp.append((axis_depth(p_mid, opening_axis), p_mid))
            edge_exp.Next()

        layers: List[dict] = []

        def add_to_layer(depth: float, radius: float, is_sharp: bool, point: gp_Pnt) -> None:
            tol = 0.5
            for layer in layers:
                if abs(depth - layer["depth"]) <= tol:
                    n = layer["count"]
                    layer["depth"] = (layer["depth"] * n + depth) / (n + 1)
                    layer["count"] = n + 1
                    layer["radii"].append(radius)
                    layer["points"].append(point)
                    if is_sharp:
                        layer["sharp"] += 1
                    return
            layers.append(
                {
                    "depth": depth,
                    "count": 1,
                    "sharp": 1 if is_sharp else 0,
                    "radii": [radius],
                    "points": [point],
                }
            )

        for depth, radius, point in rounded:
            add_to_layer(depth, radius, False, point)
        for depth, point in sharp:
            add_to_layer(depth, 0.0, True, point)

        layers_by_axis[axis_name] = layers

    return layers_by_axis


def evaluate_deep_pocket_ratio(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    layers_by_axis = detect_internal_corner_layers(shape)
    axis_specs: List[Tuple[str, gp_Dir]] = [
        ("X", gp_Dir(1.0, 0.0, 0.0)),
        ("Y", gp_Dir(0.0, 1.0, 0.0)),
        ("Z", gp_Dir(0.0, 0.0, 1.0)),
    ]
    worst_ratio = 0.0
    offenders = 0
    detected = 0

    for axis_name, axis in axis_specs:
        openings = external_axis_openings(shape, axis)
        if not openings:
            continue

        for layer in layers_by_axis.get(axis_name, []):
            if layer["count"] < 2:
                continue

            points = layer["points"]
            if len(points) < 2:
                continue

            u_vals = [axis_perp_components(p, axis_name)[0] for p in points]
            v_vals = [axis_perp_components(p, axis_name)[1] for p in points]
            u_span = max(u_vals) - min(u_vals)
            v_span = max(v_vals) - min(v_vals)
            opening_candidates = [s for s in (u_span, v_span) if s > precision.Confusion()]
            if not opening_candidates:
                continue
            opening = min(opening_candidates)

            depth = min(abs(layer["depth"] - ref) for ref in openings)
            if depth <= precision.Confusion():
                continue

            detected += 1
            ratio = depth / opening
            worst_ratio = max(worst_ratio, ratio)
            if ratio > cfg.max_pocket_depth_ratio:
                offenders += 1

    pass_count = max(detected - offenders, 0)
    fail_count = offenders
    passed = fail_count == 0
    details = (
        f"Worst corner-derived pocket depth ratio is {worst_ratio:.2f}; "
        f"maximum allowed is {cfg.max_pocket_depth_ratio:.2f}."
    )
    if offenders > 0:
        details += f" Found {offenders} likely deep pocket feature(s)."

    return RuleResult(
        name="Rule 2 — Deep Pocket Ratio",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=details,
        detected_features=detected,
        passed_features=pass_count,
        failed_features=fail_count,
    )
