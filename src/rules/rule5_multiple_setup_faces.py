from __future__ import annotations

import math
from typing import Tuple

from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.gp import gp_Dir

from dfm_geometry import collect_faces, face_area, planar_face_normal
from dfm_models import Config, RuleResult


def normalize_axis_key(normal: gp_Dir, bucket_deg: float) -> Tuple[int, int, int]:
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

    dominant = [k for k, a in axis_area.items() if a > 1.0]
    setups = len(dominant)
    fail_count = max(setups - cfg.max_setups, 0)
    pass_count = setups - fail_count
    passed = fail_count == 0
    return RuleResult(
        name="Rule 5 — Multiple Setup Faces",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=(
            f"Estimated machining setup axes: {setups}; "
            f"maximum allowed is {cfg.max_setups}."
        ),
        detected_features=setups,
        passed_features=pass_count,
        failed_features=fail_count,
    )
