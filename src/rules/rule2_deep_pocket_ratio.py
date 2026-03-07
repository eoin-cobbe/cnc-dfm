from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from OCC.Core.BRep import BRep_Tool
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_VERTEX
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape
from OCC.Core.gp import gp_Dir

from dfm_geometry import (
    face_midpoint_and_normal,
    is_wall_face_for_axis,
    shape_bbox,
    signed_distance_between_planes,
)
from dfm_models import Config, OffenderRecord, RuleResult
from dfm_scoring import rule_multiplier_from_threshold
from .rule1_internal_corner_radius import detect_internal_corner_features


def _group_corner_features_by_depth(features: List[dict], tol_mm: float = 0.5) -> List[dict]:
    layers: List[dict] = []
    for feature in features:
        depth = feature["depth_along_axis"]
        for layer in layers:
            if abs(depth - layer["depth"]) <= tol_mm:
                n = layer["count"]
                layer["depth"] = (layer["depth"] * n + depth) / (n + 1)
                layer["count"] = n + 1
                layer["features"].append(feature)
                break
        else:
            layers.append({"depth": depth, "count": 1, "features": [feature]})
    return layers


def _axis_dir(axis_name: str) -> gp_Dir:
    if axis_name == "X":
        return gp_Dir(1.0, 0.0, 0.0)
    if axis_name == "Y":
        return gp_Dir(0.0, 1.0, 0.0)
    return gp_Dir(0.0, 0.0, 1.0)


def _feature_axis_wall_faces(feature: dict, axis_dir: gp_Dir) -> List[TopoDS_Face]:
    faces: List[TopoDS_Face] = []
    for face in feature["wall_faces"]:
        if is_wall_face_for_axis(face, axis_dir):
            if all(not existing.IsSame(face) for existing in faces):
                faces.append(face)
    return faces


def _split_depth_layer_into_pockets(layer: dict, axis_name: str, shape: TopoDS_Shape) -> List[List[dict]]:
    features = layer["features"]
    if len(features) <= 1:
        return [features]
    axis_dir = _axis_dir(axis_name)

    # Primary split: connect features through shared pocket faces, ignoring globally shared faces.
    # This separates neighboring pockets that happen to be at the same depth.
    unique_faces: List[TopoDS_Face] = []
    owners: List[set] = []
    for idx, feature in enumerate(features):
        for face in _feature_axis_wall_faces(feature, axis_dir):
            found = None
            for i, existing in enumerate(unique_faces):
                if existing.IsSame(face):
                    found = i
                    break
            if found is None:
                unique_faces.append(face)
                owners.append({idx})
            else:
                owners[found].add(idx)

    neighbors: Dict[int, List[int]] = {i: [] for i in range(len(features))}
    max_shared = max(2, int(math.ceil(len(features) * 0.5)))
    for own in owners:
        if len(own) > max_shared:
            continue
        linked = sorted(list(own))
        for i in range(len(linked)):
            for j in range(i + 1, len(linked)):
                a, b = linked[i], linked[j]
                if b not in neighbors[a]:
                    neighbors[a].append(b)
                if a not in neighbors[b]:
                    neighbors[b].append(a)

    # Fallback split for sparse topology: use proximity in the pocket plane.
    if all(len(v) == 0 for v in neighbors.values()):
        from dfm_geometry import axis_perp_components

        points = [axis_perp_components(f["midpoint"], axis_name) for f in features]
        nearest: List[float] = []
        for i in range(len(points)):
            best = float("inf")
            for j in range(len(points)):
                if i == j:
                    continue
                du = points[i][0] - points[j][0]
                dv = points[i][1] - points[j][1]
                d = math.hypot(du, dv)
                if d < best:
                    best = d
            if best < float("inf"):
                nearest.append(best)

        if nearest:
            nearest_sorted = sorted(nearest)
            eps = nearest_sorted[len(nearest_sorted) // 2] * 1.8
        else:
            dx, dy, dz = shape_bbox(shape)
            eps = min(dx, dy, dz) * 0.1
        eps = max(eps, 2.0)

        for i in range(len(features)):
            for j in range(i + 1, len(features)):
                du = points[i][0] - points[j][0]
                dv = points[i][1] - points[j][1]
                d = math.hypot(du, dv)
                if d <= eps:
                    neighbors[i].append(j)
                    neighbors[j].append(i)

    pockets: List[List[dict]] = []
    seen = set()
    for i in range(len(features)):
        if i in seen:
            continue
        stack = [i]
        seen.add(i)
        comp: List[dict] = []
        while stack:
            n = stack.pop()
            comp.append(features[n])
            for m in neighbors[n]:
                if m in seen:
                    continue
                seen.add(m)
                stack.append(m)
        pockets.append(comp)
    return pockets


def _opening_from_pocket_faces(faces: List[TopoDS_Face]) -> Optional[float]:
    separations: List[float] = []
    min_parallel = math.cos(math.radians(10.0))
    for i in range(len(faces)):
        data_i = face_midpoint_and_normal(faces[i])
        if data_i is None:
            continue
        _pi, ni = data_i
        for j in range(i + 1, len(faces)):
            data_j = face_midpoint_and_normal(faces[j])
            if data_j is None:
                continue
            _pj, nj = data_j
            if abs(ni.XYZ().Dot(nj.XYZ())) < min_parallel:
                continue
            d = signed_distance_between_planes(faces[i], faces[j], ni)
            if d is None:
                continue
            sep = abs(d)
            if sep > precision.Confusion():
                separations.append(sep)
    if not separations:
        return None
    return min(separations)


def _opening_from_pocket_features(pocket_features: List[dict], axis_name: str) -> Optional[float]:
    axis_dir = _axis_dir(axis_name)
    unique_faces: List[TopoDS_Face] = []
    usage: List[int] = []
    for feature in pocket_features:
        for face in _feature_axis_wall_faces(feature, axis_dir):
            idx = None
            for i, existing in enumerate(unique_faces):
                if existing.IsSame(face):
                    idx = i
                    break
            if idx is None:
                unique_faces.append(face)
                usage.append(1)
            else:
                usage[idx] += 1

    if not unique_faces:
        return None

    min_usage = max(2, int(math.ceil(len(pocket_features) * 0.25)))
    dominant_faces = [f for f, c in zip(unique_faces, usage) if c >= min_usage]
    # Open-ended/through-corner pockets can have only one dominant wall face.
    # In that case, fall back to all pocket wall faces so opening can still be measured.
    faces = dominant_faces if len(dominant_faces) >= 2 else unique_faces

    # Build pair metrics once so we can apply robust fallbacks for sloped/non-parallel pockets.
    pair_rows = []
    min_parallel = math.cos(math.radians(10.0))
    near_parallel = math.cos(math.radians(15.0))

    def min_vertex_to_face_plane_dist(face_a: TopoDS_Face, face_b: TopoDS_Face, normal_a: gp_Dir) -> Optional[float]:
        data_a = face_midpoint_and_normal(face_a)
        if data_a is None:
            return None
        pa, _na = data_a
        vexp = TopExp_Explorer(face_b, TopAbs_VERTEX)
        best = None
        while vexp.More():
            v = topods.Vertex(vexp.Current())
            p = BRep_Tool.Pnt(v)
            d = abs(p.XYZ().Subtracted(pa.XYZ()).Dot(normal_a.XYZ()))
            if d > precision.Confusion():
                if best is None or d < best:
                    best = d
            vexp.Next()
        return best

    for i in range(len(faces)):
        data_i = face_midpoint_and_normal(faces[i])
        if data_i is None:
            continue
        _pi, ni = data_i
        for j in range(i + 1, len(faces)):
            data_j = face_midpoint_and_normal(faces[j])
            if data_j is None:
                continue
            _pj, nj = data_j
            d = signed_distance_between_planes(faces[i], faces[j], ni)
            if d is None:
                continue
            dist = abs(d)
            if dist <= precision.Confusion():
                continue
            edge_gap_a = min_vertex_to_face_plane_dist(faces[i], faces[j], ni)
            edge_gap_b = min_vertex_to_face_plane_dist(faces[j], faces[i], nj)
            edge_gap = None
            for val in (edge_gap_a, edge_gap_b):
                if val is None:
                    continue
                if edge_gap is None or val < edge_gap:
                    edge_gap = val

            shared_count = 0
            for feature in pocket_features:
                fset = _feature_axis_wall_faces(feature, axis_dir)
                has_i = any(faces[i].IsSame(ff) for ff in fset)
                has_j = any(faces[j].IsSame(ff) for ff in fset)
                if has_i and has_j:
                    shared_count += 1

            pair_rows.append(
                {
                    "dist": dist,
                    "dot": ni.XYZ().Dot(nj.XYZ()),
                    "shared": shared_count,
                    "strict_parallel": abs(ni.XYZ().Dot(nj.XYZ())) >= min_parallel,
                    "near_parallel": abs(ni.XYZ().Dot(nj.XYZ())) >= near_parallel,
                    "edge_gap": edge_gap,
                }
            )

    if not pair_rows:
        return None

    strict = sorted([row["dist"] for row in pair_rows if row["strict_parallel"]])
    if strict:
        opening = strict[0]
        # Edge case: sloped pockets may have only one strict parallel pair (the long direction).
        # Prefer near-parallel face/edge gap in that case, otherwise use adjacent-pair median.
        if len(strict) <= 1:
            near_gaps = sorted(
                row["edge_gap"]
                for row in pair_rows
                if row["near_parallel"] and not row["strict_parallel"] and row["edge_gap"] is not None
            )
            if near_gaps:
                opening = min(opening, near_gaps[0])
            else:
                adjacent = sorted([row["dist"] for row in pair_rows if row["shared"] > 0])
                if len(adjacent) >= 2:
                    mid = len(adjacent) // 2
                    if len(adjacent) % 2 == 0:
                        median_adj = 0.5 * (adjacent[mid - 1] + adjacent[mid])
                    else:
                        median_adj = adjacent[mid]
                    opening = min(opening, median_adj)
        return opening

    return min(row["dist"] for row in pair_rows)


def evaluate_deep_pocket_ratio(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    features_by_axis = detect_internal_corner_features(shape)
    axis_breakdown: Dict[str, Tuple[int, int, int]] = {}
    detected = 0
    offenders = 0
    worst_ratio = 0.0
    ratios: List[float] = []
    offender_records: List[OffenderRecord] = []

    for axis_name, axis_features in features_by_axis.items():
        layers = _group_corner_features_by_depth(axis_features, tol_mm=0.5)
        axis_detected = 0
        axis_offenders = 0
        for layer in layers:
            for pocket_features in _split_depth_layer_into_pockets(layer, axis_name, shape):
                if len(pocket_features) < 2:
                    continue

                opening = _opening_from_pocket_features(pocket_features, axis_name)
                if opening is None or opening <= precision.Confusion():
                    continue

                depth = max(feature["cylindrical_depth"] for feature in pocket_features)
                if depth <= precision.Confusion():
                    continue

                axis_detected += 1
                ratio = depth / opening
                ratios.append(ratio)
                worst_ratio = max(worst_ratio, ratio)
                if ratio > cfg.max_pocket_depth_ratio:
                    axis_offenders += 1
                    avg_x = sum(feature["midpoint"].X() for feature in pocket_features) / len(pocket_features)
                    avg_y = sum(feature["midpoint"].Y() for feature in pocket_features) / len(pocket_features)
                    avg_z = sum(feature["midpoint"].Z() for feature in pocket_features) / len(pocket_features)
                    target_depth = cfg.max_pocket_depth_ratio * opening
                    offender_records.append(
                        OffenderRecord(
                            rule_id="R2",
                            metric="Depth/Open Ratio",
                            current_value=ratio,
                            target_value=cfg.max_pocket_depth_ratio,
                            delta=ratio - cfg.max_pocket_depth_ratio,
                            occ_anchor={
                                "centroid": {"x": avg_x, "y": avg_y, "z": avg_z},
                                "dominant_axis": axis_name,
                                "local_dimensions": {
                                    "depth_mm": depth,
                                    "opening_mm": opening,
                                    "target_depth_mm": target_depth,
                                },
                            },
                            supported_remediations=["extrude.depth"],
                            auto_remediable=True,
                            meta={
                                "depth_mm": depth,
                                "opening_mm": opening,
                                "target_depth_mm": target_depth,
                            },
                        )
                    )

        axis_pass = max(axis_detected - axis_offenders, 0)
        axis_breakdown[axis_name] = (axis_detected, axis_pass, axis_offenders)
        detected += axis_detected
        offenders += axis_offenders

    pass_count = max(detected - offenders, 0)
    fail_count = offenders
    passed = fail_count == 0
    avg_ratio = (sum(ratios) / len(ratios)) if ratios else 0.0
    rule_mult = rule_multiplier_from_threshold(
        average_detected=avg_ratio,
        threshold=cfg.max_pocket_depth_ratio,
        threshold_kind="max",
    )
    details = (
        f"Worst pocket depth ratio is {worst_ratio:.2f}; "
        f"maximum allowed is {cfg.max_pocket_depth_ratio:.2f}. "
        f"Pockets require >=2 radiused internal corners; depth comes from cylindrical corner depth; "
        f"opening comes from opposing pocket wall faces."
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
        axis_breakdown=axis_breakdown,
        metric_label="Depth/Open Ratio",
        average_detected=avg_ratio,
        threshold=cfg.max_pocket_depth_ratio,
        threshold_kind="max",
        rule_multiplier=rule_mult,
        offenders=offender_records,
    )
