from __future__ import annotations

import math
from typing import List, Optional, Tuple

from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepLProp import BRepLProp_SLProps
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAbs import GeomAbs_Plane
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.Precision import precision
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_IN
from OCC.Core.TopExp import TopExp_Explorer, topexp
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_ListIteratorOfListOfShape
from OCC.Core.gp import gp_Dir, gp_Pnt


def read_step(path: str) -> TopoDS_Shape:
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP file: {path}")
    transfer_ok = reader.TransferRoots()
    if transfer_ok == 0:
        raise RuntimeError(f"No transferable geometry in STEP file: {path}")
    shape = reader.Shape()
    if shape.IsNull():
        raise RuntimeError(f"Loaded shape is null: {path}")
    return shape


def shape_bbox(shape: TopoDS_Shape) -> Tuple[float, float, float]:
    box = Bnd_Box()
    brepbndlib.Add(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return max(0.0, xmax - xmin), max(0.0, ymax - ymin), max(0.0, zmax - zmin)


def collect_faces(shape: TopoDS_Shape) -> List[TopoDS_Face]:
    faces: List[TopoDS_Face] = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        faces.append(topods.Face(exp.Current()))
        exp.Next()
    return faces


def face_area(face: TopoDS_Face) -> float:
    props = GProp_GProps()
    brepgprop.SurfaceProperties(face, props)
    return props.Mass()


def shape_centroid(shape: TopoDS_Shape) -> gp_Pnt:
    props = GProp_GProps()
    brepgprop.VolumeProperties(shape, props)
    return props.CentreOfMass()


def get_edge_face_map(shape: TopoDS_Shape) -> TopTools_IndexedDataMapOfShapeListOfShape:
    mapping = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, mapping)
    return mapping


def faces_for_edge(edge_face_map: TopTools_IndexedDataMapOfShapeListOfShape, edge) -> List[TopoDS_Face]:
    if not edge_face_map.Contains(edge):
        return []
    faces: List[TopoDS_Face] = []
    lst = edge_face_map.FindFromKey(edge)
    it = TopTools_ListIteratorOfListOfShape(lst)
    while it.More():
        faces.append(topods.Face(it.Value()))
        it.Next()
    return faces


def face_midpoint_and_normal(face: TopoDS_Face) -> Optional[Tuple[gp_Pnt, gp_Dir]]:
    surf = BRepAdaptor_Surface(face)
    u1, u2 = surf.FirstUParameter(), surf.LastUParameter()
    v1, v2 = surf.FirstVParameter(), surf.LastVParameter()
    u = (u1 + u2) * 0.5
    v = (v1 + v2) * 0.5
    props = BRepLProp_SLProps(surf, u, v, 1, precision.Confusion())
    if not props.IsNormalDefined():
        return None
    return surf.Value(u, v), props.Normal()


def is_internal_face(face: TopoDS_Face, centroid: gp_Pnt) -> bool:
    data = face_midpoint_and_normal(face)
    if data is None:
        return False
    point, normal = data
    vec = point.XYZ().Subtracted(centroid.XYZ())
    return normal.XYZ().Dot(vec) < 0.0


def offset_is_outside(shape: TopoDS_Shape, point: gp_Pnt, direction: gp_Dir, distance: float = 0.2) -> bool:
    probe = gp_Pnt(
        point.X() + direction.X() * distance,
        point.Y() + direction.Y() * distance,
        point.Z() + direction.Z() * distance,
    )
    classifier = BRepClass3d_SolidClassifier(shape, probe, precision.Confusion())
    return classifier.State() != TopAbs_IN


def is_wall_face_for_axis(face: TopoDS_Face, axis: gp_Dir) -> bool:
    data = face_midpoint_and_normal(face)
    if data is None:
        return False
    _point, normal = data
    return abs(normal.XYZ().Dot(axis.XYZ())) < 0.35


def is_parallel(a: gp_Dir, b: gp_Dir, max_angle_deg: float) -> bool:
    return abs(a.XYZ().Dot(b.XYZ())) >= math.cos(math.radians(max_angle_deg))


def axis_depth(point: gp_Pnt, axis: gp_Dir) -> float:
    return point.X() * axis.X() + point.Y() * axis.Y() + point.Z() * axis.Z()


def axis_perp_components(point: gp_Pnt, axis_name: str) -> Tuple[float, float]:
    if axis_name == "X":
        return point.Y(), point.Z()
    if axis_name == "Y":
        return point.X(), point.Z()
    return point.X(), point.Y()


def external_axis_openings(shape: TopoDS_Shape, axis: gp_Dir) -> List[float]:
    centroid = shape_centroid(shape)
    openings: List[float] = []
    face_exp = TopExp_Explorer(shape, TopAbs_FACE)
    while face_exp.More():
        face = topods.Face(face_exp.Current())
        surf = BRepAdaptor_Surface(face)
        if surf.GetType() != GeomAbs_Plane:
            face_exp.Next()
            continue
        data = face_midpoint_and_normal(face)
        if data is None:
            face_exp.Next()
            continue
        point, normal = data
        if not is_parallel(normal, axis, 20.0):
            face_exp.Next()
            continue
        if is_internal_face(face, centroid):
            face_exp.Next()
            continue
        openings.append(axis_depth(point, axis))
        face_exp.Next()
    return openings


def planar_face_normal(face: TopoDS_Face) -> Optional[gp_Dir]:
    surf = BRepAdaptor_Surface(face)
    if surf.GetType() != GeomAbs_Plane:
        return None
    u1, u2 = surf.FirstUParameter(), surf.LastUParameter()
    v1, v2 = surf.FirstVParameter(), surf.LastVParameter()
    u = (u1 + u2) * 0.5
    v = (v1 + v2) * 0.5
    props = BRepLProp_SLProps(surf, u, v, 1, precision.Confusion())
    if not props.IsNormalDefined():
        return None
    return props.Normal()


def signed_distance_between_planes(
    face_a: TopoDS_Face, face_b: TopoDS_Face, normal_a: gp_Dir
) -> Optional[float]:
    surf_a = BRepAdaptor_Surface(face_a)
    surf_b = BRepAdaptor_Surface(face_b)
    if surf_a.GetType() != GeomAbs_Plane or surf_b.GetType() != GeomAbs_Plane:
        return None
    ua = (surf_a.FirstUParameter() + surf_a.LastUParameter()) * 0.5
    va = (surf_a.FirstVParameter() + surf_a.LastVParameter()) * 0.5
    ub = (surf_b.FirstUParameter() + surf_b.LastUParameter()) * 0.5
    vb = (surf_b.FirstVParameter() + surf_b.LastVParameter()) * 0.5
    pa = surf_a.Value(ua, va)
    pb = surf_b.Value(ub, vb)
    vec = gp_Pnt(pb.X(), pb.Y(), pb.Z()).XYZ().Subtracted(pa.XYZ())
    return vec.Dot(normal_a.XYZ())
