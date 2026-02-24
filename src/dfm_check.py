#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
from OCC.Core.BRepGProp import brepgprop
from OCC.Core.BRepLProp import BRepLProp_SLProps
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Plane
from OCC.Core.gp import gp_Dir, gp_Pnt
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.Precision import precision
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_IN
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Shape, topods


@dataclass
class RuleResult:
    name: str
    passed: bool
    summary: str
    details: str


@dataclass
class Config:
    min_internal_corner_radius_mm: float = 1.0
    max_pocket_depth_ratio: float = 4.0
    min_wall_thickness_mm: float = 1.0
    max_hole_depth_to_diameter: float = 6.0
    max_setups: int = 2
    normal_similarity_deg: float = 12.0


class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"


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


def edge_length(edge) -> float:
    props = GProp_GProps()
    brepgprop.LinearProperties(edge, props)
    return props.Mass()


def use_color() -> bool:
    return os.getenv("TERM") is not None and os.getenv("NO_COLOR") is None


def paint(text: str, *styles: str) -> str:
    if not use_color():
        return text
    return f"{''.join(styles)}{text}{Ansi.RESET}"


def status_text(passed: bool) -> str:
    return paint("PASS", Ansi.BOLD, Ansi.GREEN) if passed else paint("FAIL", Ansi.BOLD, Ansi.RED)


def icon(passed: bool) -> str:
    return paint("OK", Ansi.GREEN) if passed else paint("XX", Ansi.RED)


def print_block_logo() -> None:
    lines = [
        "  ######  ##    ##  ######          ######   ######## ##     ## ",
        " ##    ## ###   ## ##    ##        ##    ##  ##       ###   ### ",
        " ##       ####  ## ##              ##        ##       #### #### ",
        " ##       ## ## ## ##              ##   #### ######   ## ### ## ",
        " ##       ##  #### ##              ##    ##  ##       ##     ## ",
        " ##    ## ##   ### ##    ##        ##    ##  ##       ##     ## ",
        "  ######  ##    ##  ######          ######   ##       ##     ## ",
    ]
    for line in lines:
        print(paint(line, Ansi.BOLD, Ansi.CYAN))


def print_boot(step_file: str) -> None:
    inner_width = 62

    def line(text: str) -> None:
        clipped = text[:inner_width]
        print(paint(f"| {clipped.ljust(inner_width)} |", Ansi.BLUE))

    print_block_logo()
    print(paint("+----------------------------------------------------------------+", Ansi.CYAN))
    print(paint("| CNC-DFM onboarding                                              |", Ansi.CYAN))
    print(paint("+----------------------------------------------------------------+", Ansi.CYAN))
    line("[BOOT] Runtime online")
    line("[LOAD] STEP parser (pythonOCC) ready")
    line(f"[FILE] {step_file}")
    line("[CHECK] Running 5 DFM rules")
    print(paint("+----------------------------------------------------------------+", Ansi.CYAN))
    print("")


def evaluate_internal_corner_radius(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    radii: List[float] = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        edge = topods.Edge(exp.Current())
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() == GeomAbs_Circle:
            radii.append(curve.Circle().Radius())
        exp.Next()

    if not radii:
        return RuleResult(
            name="Rule 1 — Internal Corner Radius Too Small",
            passed=True,
            summary="PASS",
            details="No circular edges found, so no small corner radii were detected.",
        )

    min_radius = min(radii)
    passed = min_radius >= cfg.min_internal_corner_radius_mm
    return RuleResult(
        name="Rule 1 — Internal Corner Radius Too Small",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Minimum detected edge radius is {min_radius:.3f} mm; "
            f"required minimum is {cfg.min_internal_corner_radius_mm:.3f} mm."
        ),
    )


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


def planar_face_size(face: TopoDS_Face) -> Tuple[float, float, float]:
    box = Bnd_Box()
    brepbndlib.Add(face, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    dx, dy, dz = max(0.0, xmax - xmin), max(0.0, ymax - ymin), max(0.0, zmax - zmin)
    dims = sorted([dx, dy, dz], reverse=True)
    return dims[0], dims[1], dims[2]


def signed_distance_between_planes(
    face_a: TopoDS_Face, face_b: TopoDS_Face, normal_a: gp_Dir
) -> Optional[float]:
    # Distance of center point of face_b to plane of face_a along normal_a
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


def evaluate_deep_pocket_ratio(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    faces = collect_faces(shape)
    planar = [(f, planar_face_normal(f), face_area(f)) for f in faces]
    planar = [(f, n, a) for f, n, a in planar if n is not None]

    worst_ratio = 0.0
    offenders = 0

    for face, normal, area in planar:
        l1, l2, _ = planar_face_size(face)
        opening = min(l1, l2)
        if opening <= precision.Confusion():
            continue

        best_depth = 0.0
        for other, onormal, oarea in planar:
            if other.IsSame(face):
                continue
            if normal.Angle(onormal) > math.radians(cfg.normal_similarity_deg):
                continue
            dist = signed_distance_between_planes(face, other, normal)
            if dist is None:
                continue
            best_depth = max(best_depth, abs(dist))

        if best_depth <= precision.Confusion():
            continue

        ratio = best_depth / opening
        worst_ratio = max(worst_ratio, ratio)
        if ratio > cfg.max_pocket_depth_ratio:
            offenders += 1

    passed = offenders == 0
    details = (
        f"Worst estimated pocket depth ratio is {worst_ratio:.2f}; "
        f"maximum allowed is {cfg.max_pocket_depth_ratio:.2f}."
    )
    if offenders > 0:
        details += f" Found {offenders} likely deep pocket feature(s)."

    return RuleResult(
        name="Rule 2 — Deep Pocket Ratio",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=details,
    )


def evaluate_thin_walls(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    dx, dy, dz = shape_bbox(shape)
    min_envelope = min(dx, dy, dz)
    passed = min_envelope >= cfg.min_wall_thickness_mm
    return RuleResult(
        name="Rule 3 — Thin Walls",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Minimum global envelope thickness is {min_envelope:.3f} mm; "
            f"required minimum wall thickness is {cfg.min_wall_thickness_mm:.3f} mm."
        ),
    )


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
        center = BRepAdaptor_Surface(face).Value(
            (BRepAdaptor_Surface(face).FirstUParameter() + BRepAdaptor_Surface(face).LastUParameter()) * 0.5,
            (BRepAdaptor_Surface(face).FirstVParameter() + BRepAdaptor_Surface(face).LastVParameter()) * 0.5,
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
        )

    worst = max(ratios)
    passed = worst <= cfg.max_hole_depth_to_diameter
    return RuleResult(
        name="Rule 4 — Hole Depth vs Diameter",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Worst detected hole depth/diameter ratio is {worst:.2f}; "
            f"maximum allowed is {cfg.max_hole_depth_to_diameter:.2f}."
        ),
    )


def normalize_axis_key(normal: gp_Dir, bucket_deg: float) -> Tuple[int, int, int]:
    # Treat opposite directions as same setup axis.
    x, y, z = abs(normal.X()), abs(normal.Y()), abs(normal.Z())
    scale = 1.0 / max(math.sin(math.radians(bucket_deg)), 1e-6)
    return int(round(x * scale)), int(round(y * scale)), int(round(z * scale))


def evaluate_multiple_setup_faces(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    faces = collect_faces(shape)
    axis_area = {}
    for face in faces:
        n = planar_face_normal(face)
        if n is None:
            continue
        a = face_area(face)
        key = normalize_axis_key(n, cfg.normal_similarity_deg)
        axis_area[key] = axis_area.get(key, 0.0) + a

    # Keep only dominant machining faces to reduce noise.
    dominant = [k for k, a in axis_area.items() if a > 1.0]
    setups = len(dominant)
    passed = setups <= cfg.max_setups
    return RuleResult(
        name="Rule 5 — Multiple Setup Faces",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Estimated machining setup axes: {setups}; "
            f"maximum allowed is {cfg.max_setups}."
        ),
    )


def run_all_rules(shape: TopoDS_Shape, cfg: Config) -> List[RuleResult]:
    return [
        evaluate_internal_corner_radius(shape, cfg),
        evaluate_deep_pocket_ratio(shape, cfg),
        evaluate_thin_walls(shape, cfg),
        evaluate_hole_depth_vs_diameter(shape, cfg),
        evaluate_multiple_setup_faces(shape, cfg),
    ]


def print_report(results: List[RuleResult], file_path: str) -> None:
    print(paint("+----------------------------------------------------------------+", Ansi.CYAN))
    print(paint("| CNC-DFM :: Geometry Boot Check                                 |", Ansi.CYAN))
    print(paint("+----------------------------------------------------------------+", Ansi.CYAN))
    print(f"{paint('FILE', Ansi.BOLD, Ansi.BLUE)}  {file_path}")
    print(paint("-" * 72, Ansi.GRAY))

    for idx, result in enumerate(results, start=1):
        print(f"{icon(result.passed)}  {paint(f'R{idx}', Ansi.BOLD, Ansi.CYAN)}  {result.name}")
        print(f"    {paint('RESULT', Ansi.BOLD)}  {status_text(result.passed)}")
        print(f"    {paint('DETAIL', Ansi.DIM)}   {result.details}")
        print("")

    print(paint("-" * 72, Ansi.GRAY))
    passed_count = sum(1 for r in results if r.passed)
    overall_pass = passed_count == len(results)
    print(
        f"{paint('SUMMARY', Ansi.BOLD, Ansi.BLUE)}  "
        f"{passed_count}/{len(results)} passed  "
        f"{status_text(overall_pass)}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI DFM checker for STEP files (pythonOCC)."
    )
    parser.add_argument("step_file", help="Path to input STEP file")
    parser.add_argument("--min-radius", type=float, default=1.0, help="Rule 1 min internal radius (mm)")
    parser.add_argument("--max-pocket-ratio", type=float, default=4.0, help="Rule 2 max pocket depth ratio")
    parser.add_argument("--min-wall", type=float, default=1.0, help="Rule 3 min wall thickness (mm)")
    parser.add_argument("--max-hole-ratio", type=float, default=6.0, help="Rule 4 max hole depth/diameter ratio")
    parser.add_argument("--max-setups", type=int, default=2, help="Rule 5 max setup faces/axes")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = Config(
        min_internal_corner_radius_mm=args.min_radius,
        max_pocket_depth_ratio=args.max_pocket_ratio,
        min_wall_thickness_mm=args.min_wall,
        max_hole_depth_to_diameter=args.max_hole_ratio,
        max_setups=args.max_setups,
    )
    print_boot(args.step_file)
    shape = read_step(args.step_file)
    results = run_all_rules(shape, cfg)
    print_report(results, args.step_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
