from __future__ import annotations

from typing import Iterable, Tuple

from OCC.Core.gp import gp_Pnt

from dfm_models import Point3D


Bounds = Tuple[float, float, float, float, float, float]


def format_mm(value: float) -> str:
    return f"{value:.2f} mm"


def format_ratio(value: float) -> str:
    return f"{value:.2f}"


def average_point(points: Iterable[gp_Pnt]) -> gp_Pnt:
    rows = list(points)
    if not rows:
        return gp_Pnt(0.0, 0.0, 0.0)
    count = float(len(rows))
    return gp_Pnt(
        sum(point.X() for point in rows) / count,
        sum(point.Y() for point in rows) / count,
        sum(point.Z() for point in rows) / count,
    )


def point_axis_value(point: gp_Pnt, axis_name: str) -> float:
    if axis_name == "X":
        return point.X()
    if axis_name == "Y":
        return point.Y()
    return point.Z()


def axis_bounds(bounds: Bounds, axis_name: str) -> Tuple[float, float]:
    xmin, ymin, zmin, xmax, ymax, zmax = bounds
    if axis_name == "X":
        return xmin, xmax
    if axis_name == "Y":
        return ymin, ymax
    return zmin, zmax


def nearest_axis_side(point: gp_Pnt, bounds: Bounds, axis_name: str) -> str:
    axis_min, axis_max = axis_bounds(bounds, axis_name)
    value = point_axis_value(point, axis_name)
    if abs(value - axis_min) <= abs(value - axis_max):
        return f"-{axis_name}"
    return f"+{axis_name}"


def point3d(point: gp_Pnt) -> Point3D:
    return Point3D(x=point.X(), y=point.Y(), z=point.Z())


def feature_id(prefix: str, *values: object) -> str:
    normalized = "-".join(str(value).replace(" ", "_") for value in values)
    return f"{prefix}-{normalized}"
