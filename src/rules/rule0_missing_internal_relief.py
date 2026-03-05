from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.Precision import precision
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCC.Core.TopExp import TopExp_Explorer, topexp
from OCC.Core.TopoDS import TopoDS_Edge, TopoDS_Face, TopoDS_Shape, TopoDS_Vertex, topods
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_ListIteratorOfListOfShape
from OCC.Core.gp import gp_Dir

from dfm_geometry import (
    face_midpoint_and_normal,
    faces_for_edge,
    get_edge_face_map,
    is_internal_face,
    offset_is_outside,
    shape_bbox,
    shape_centroid,
)
from dfm_models import Config, RuleResult

AXIS_DIRS: Dict[str, gp_Dir] = {
    "X": gp_Dir(1.0, 0.0, 0.0),
    "Y": gp_Dir(0.0, 1.0, 0.0),
    "Z": gp_Dir(0.0, 0.0, 1.0),
}


def _vertex_face_map(shape: TopoDS_Shape) -> TopTools_IndexedDataMapOfShapeListOfShape:
    mapping = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(shape, TopAbs_VERTEX, TopAbs_FACE, mapping)
    return mapping


def _vertex_edge_map(shape: TopoDS_Shape) -> TopTools_IndexedDataMapOfShapeListOfShape:
    mapping = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(shape, TopAbs_VERTEX, TopAbs_EDGE, mapping)
    return mapping


def _faces_for_vertex(
    vertex_face_map: TopTools_IndexedDataMapOfShapeListOfShape, vertex: TopoDS_Vertex
) -> List[TopoDS_Face]:
    if not vertex_face_map.Contains(vertex):
        return []
    faces: List[TopoDS_Face] = []
    lst = vertex_face_map.FindFromKey(vertex)
    it = TopTools_ListIteratorOfListOfShape(lst)
    while it.More():
        faces.append(topods.Face(it.Value()))
        it.Next()
    return faces


def _edges_for_vertex(
    vertex_edge_map: TopTools_IndexedDataMapOfShapeListOfShape, vertex: TopoDS_Vertex
) -> List[TopoDS_Edge]:
    if not vertex_edge_map.Contains(vertex):
        return []
    edges: List[TopoDS_Edge] = []
    lst = vertex_edge_map.FindFromKey(vertex)
    it = TopTools_ListIteratorOfListOfShape(lst)
    while it.More():
        edges.append(topods.Edge(it.Value()))
        it.Next()
    return edges


def _unique_faces(faces: List[TopoDS_Face]) -> List[TopoDS_Face]:
    unique: List[TopoDS_Face] = []
    for face in faces:
        if all(not existing.IsSame(face) for existing in unique):
            unique.append(face)
    return unique


def _dominant_axis_from_edge(edge: TopoDS_Edge) -> Optional[str]:
    v_start = topods.Vertex(topexp.FirstVertex(edge))
    v_end = topods.Vertex(topexp.LastVertex(edge))
    if v_start.IsNull() or v_end.IsNull():
        return None
    p_start = BRep_Tool.Pnt(v_start)
    p_end = BRep_Tool.Pnt(v_end)
    components = {
        "X": abs(p_end.X() - p_start.X()),
        "Y": abs(p_end.Y() - p_start.Y()),
        "Z": abs(p_end.Z() - p_start.Z()),
    }
    axis = max(components, key=components.get)
    if components[axis] <= precision.Confusion():
        return None
    return axis


def _planar_face_normal(face: TopoDS_Face) -> Optional[gp_Dir]:
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Plane:
        return None
    data = face_midpoint_and_normal(face)
    if data is None:
        return None
    _point, normal = data
    return normal


def _is_wall_for_axis(normal: gp_Dir, axis_name: str, max_angle_deg: float = 15.0) -> bool:
    return abs(normal.XYZ().Dot(AXIS_DIRS[axis_name].XYZ())) <= math.sin(math.radians(max_angle_deg))


def _is_parallel_to_axis(normal: gp_Dir, axis_name: str, max_angle_deg: float = 15.0) -> bool:
    return abs(normal.XYZ().Dot(AXIS_DIRS[axis_name].XYZ())) >= math.cos(math.radians(max_angle_deg))


def _endpoint_axial_face_counts(
    vertex: TopoDS_Vertex,
    edge_faces: List[TopoDS_Face],
    axis_name: str,
    vertex_face_map: TopTools_IndexedDataMapOfShapeListOfShape,
    centroid,
) -> Tuple[int, int]:
    min_axis_dot = math.cos(math.radians(15.0))
    axial_internal = 0
    axial_external = 0

    for face in _unique_faces(_faces_for_vertex(vertex_face_map, vertex)):
        if any(face.IsSame(edge_face) for edge_face in edge_faces):
            continue
        normal = _planar_face_normal(face)
        if normal is None:
            continue
        if abs(normal.XYZ().Dot(AXIS_DIRS[axis_name].XYZ())) < min_axis_dot:
            continue
        if is_internal_face(face, centroid):
            axial_internal += 1
        else:
            axial_external += 1

    return axial_internal, axial_external


def _shape_bounds(shape: TopoDS_Shape) -> Tuple[float, float, float, float, float, float]:
    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    return box.Get()


def _is_on_outer_silhouette(
    midpoint: Tuple[float, float, float],
    axis_name: str,
    bounds: Tuple[float, float, float, float, float, float],
    tol: float = 1e-3,
) -> bool:
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    if axis_name == "X":
        return (
            abs(midpoint[1] - ymin) <= tol
            or abs(midpoint[1] - ymax) <= tol
            or abs(midpoint[2] - zmin) <= tol
            or abs(midpoint[2] - zmax) <= tol
        )
    if axis_name == "Y":
        return (
            abs(midpoint[0] - xmin) <= tol
            or abs(midpoint[0] - xmax) <= tol
            or abs(midpoint[2] - zmin) <= tol
            or abs(midpoint[2] - zmax) <= tol
        )
    return (
        abs(midpoint[0] - xmin) <= tol
        or abs(midpoint[0] - xmax) <= tol
        or abs(midpoint[1] - ymin) <= tol
        or abs(midpoint[1] - ymax) <= tol
    )


def _is_clear_approach(shape: TopoDS_Shape, point, direction: gp_Dir) -> bool:
    bbox = shape_bbox(shape)
    max_travel = max(bbox) + math.sqrt(bbox[0] ** 2 + bbox[1] ** 2 + bbox[2] ** 2) + 2.0
    step = 0.5
    distance = step
    while distance <= max_travel:
        if not offset_is_outside(shape, point, direction, distance=distance):
            return False
        distance += step
    return True


def _has_accessible_internal_floor(shape: TopoDS_Shape, axis_name: str, centroid) -> bool:
    face_exp = TopExp_Explorer(shape, TopAbs_FACE)
    while face_exp.More():
        face = topods.Face(face_exp.Current())
        face_exp.Next()
        data = face_midpoint_and_normal(face)
        if data is None:
            continue
        point, normal = data
        if _planar_face_normal(face) is None:
            continue
        if not _is_parallel_to_axis(normal, axis_name):
            continue
        if not is_internal_face(face, centroid):
            continue
        if not offset_is_outside(shape, point, normal, distance=0.3):
            continue
        if _is_clear_approach(shape, point, normal):
            return True
    return False


def _is_sharp_internal_wall_edge(
    edge: TopoDS_Edge,
    axis_name: str,
    edge_face_map: TopTools_IndexedDataMapOfShapeListOfShape,
    centroid,
) -> bool:
    if _dominant_axis_from_edge(edge) != axis_name:
        return False
    faces = _unique_faces(faces_for_edge(edge_face_map, edge))
    if len(faces) != 2:
        return False
    normals: List[gp_Dir] = []
    internal_flags: List[bool] = []
    for face in faces:
        normal = _planar_face_normal(face)
        if normal is None or not _is_wall_for_axis(normal, axis_name):
            return False
        normals.append(normal)
        internal_flags.append(is_internal_face(face, centroid))
    if abs(normals[0].XYZ().Dot(normals[1].XYZ())) >= math.cos(math.radians(10.0)):
        return False
    return any(internal_flags)


def _edge_length(edge: TopoDS_Edge) -> float:
    v_start = topods.Vertex(topexp.FirstVertex(edge))
    v_end = topods.Vertex(topexp.LastVertex(edge))
    if v_start.IsNull() or v_end.IsNull():
        return 0.0
    p_start = BRep_Tool.Pnt(v_start)
    p_end = BRep_Tool.Pnt(v_end)
    dx = p_end.X() - p_start.X()
    dy = p_end.Y() - p_start.Y()
    dz = p_end.Z() - p_start.Z()
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _is_shortest_candidate_at_vertex(
    vertex: TopoDS_Vertex,
    current_edge: TopoDS_Edge,
    axis_name: str,
    vertex_edge_map: TopTools_IndexedDataMapOfShapeListOfShape,
    edge_face_map: TopTools_IndexedDataMapOfShapeListOfShape,
    centroid,
) -> bool:
    current_length = _edge_length(current_edge)
    if current_length <= precision.Confusion():
        return False

    for edge in _edges_for_vertex(vertex_edge_map, vertex):
        if edge.IsSame(current_edge):
            continue
        other_axis = _dominant_axis_from_edge(edge)
        if other_axis is None or other_axis == axis_name:
            continue
        if _is_sharp_internal_wall_edge(edge, other_axis, edge_face_map, centroid):
            if _edge_length(edge) + 1e-3 < current_length:
                return False
    return True


def evaluate_missing_internal_relief(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    del cfg

    centroid = shape_centroid(shape)
    bounds = _shape_bounds(shape)
    edge_face_map = get_edge_face_map(shape)
    vertex_face_map = _vertex_face_map(shape)
    vertex_edge_map = _vertex_edge_map(shape)
    axis_failures: Dict[str, int] = {"X": 0, "Y": 0, "Z": 0}
    seen_edges: set[Tuple[str, float, float, float]] = set()
    axes_with_accessible_floors = {
        axis_name for axis_name in ("X", "Y", "Z") if _has_accessible_internal_floor(shape, axis_name, centroid)
    }

    edge_exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while edge_exp.More():
        edge = topods.Edge(edge_exp.Current())
        edge_exp.Next()

        axis_name = _dominant_axis_from_edge(edge)
        if axis_name is None:
            continue

        faces = _unique_faces(faces_for_edge(edge_face_map, edge))
        if len(faces) != 2:
            continue

        normals: List[gp_Dir] = []
        internal_flags: List[bool] = []
        for face in faces:
            normal = _planar_face_normal(face)
            if normal is None or not _is_wall_for_axis(normal, axis_name):
                normals = []
                break
            normals.append(normal)
            internal_flags.append(is_internal_face(face, centroid))
        if len(normals) != 2:
            continue

        # Ignore collinear/parallel walls; we only want sharp wall-wall corners.
        if abs(normals[0].XYZ().Dot(normals[1].XYZ())) >= math.cos(math.radians(10.0)):
            continue

        v_start = topods.Vertex(topexp.FirstVertex(edge))
        v_end = topods.Vertex(topexp.LastVertex(edge))
        if v_start.IsNull() or v_end.IsNull():
            continue

        end_a = _endpoint_axial_face_counts(v_start, faces, axis_name, vertex_face_map, centroid)
        end_b = _endpoint_axial_face_counts(v_end, faces, axis_name, vertex_face_map, centroid)
        a_has_floor = end_a[0] > 0
        b_has_floor = end_b[0] > 0
        a_is_open = end_a[0] == 0 and end_a[1] > 0
        b_is_open = end_b[0] == 0 and end_b[1] > 0

        p_start = BRep_Tool.Pnt(v_start)
        p_end = BRep_Tool.Pnt(v_end)
        midpoint = (
            (p_start.X() + p_end.X()) * 0.5,
            (p_start.Y() + p_end.Y()) * 0.5,
            (p_start.Z() + p_end.Z()) * 0.5,
        )

        # Two broad defect cases:
        # 1) both ends are open/top: pure side-corner edge inside an open feature.
        # 2) one end lands on an internal floor and the other is open/top: blind/open pocket side edge.
        is_missing_relief = False
        if a_is_open and b_is_open:
            if not _is_on_outer_silhouette(midpoint, axis_name, bounds):
                is_missing_relief = True
        elif (
            any(internal_flags)
            and
            axis_name in axes_with_accessible_floors
            and ((a_has_floor and b_is_open) or (b_has_floor and a_is_open))
            and not _is_on_outer_silhouette(midpoint, axis_name, bounds)
        ):
            floor_vertex = v_start if a_has_floor else v_end
            if _is_shortest_candidate_at_vertex(
                floor_vertex, edge, axis_name, vertex_edge_map, edge_face_map, centroid
            ):
                is_missing_relief = True

        if not is_missing_relief:
            continue

        key = (axis_name, round(midpoint[0], 3), round(midpoint[1], 3), round(midpoint[2], 3))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        axis_failures[axis_name] += 1

    failed = sum(axis_failures.values())
    axis_breakdown = {axis_name: (count, 0, count) for axis_name, count in axis_failures.items()}

    if failed == 0:
        return RuleResult(
            name="Rule 0 — Missing Internal Relief",
            passed=True,
            summary="PASS",
            details="No missing wall-wall side-corner relief edges were found.",
            detected_features=0,
            passed_features=0,
            failed_features=0,
            axis_breakdown=axis_breakdown,
        )

    return RuleResult(
        name="Rule 0 — Missing Internal Relief",
        passed=False,
        summary="FAIL",
        details=(
            "Sharp wall-wall side-corner edges were found using edge direction, endpoint topology, "
            "and an outer-silhouette exclusion for open mouths."
        ),
        detected_features=failed,
        passed_features=0,
        failed_features=failed,
        axis_breakdown=axis_breakdown,
    )
