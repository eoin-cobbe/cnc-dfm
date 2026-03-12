from __future__ import annotations

import hashlib
from pathlib import Path

from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Shape

from dfm_geometry import read_step


def preview_cache_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "cache" / "previews"


def preview_mesh_path(step_file: str, suffix: str = ".stl") -> Path:
    source = Path(step_file).expanduser().resolve()
    stat = source.stat()
    fingerprint = hashlib.sha256(
        f"{source}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8")
    ).hexdigest()[:16]
    return preview_cache_dir() / f"{source.stem}-{fingerprint}{suffix}"


def overlay_cache_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "cache" / "feature-overlays"


def overlay_mesh_path(step_file: str, overlay_id: str, suffix: str = ".stl") -> Path:
    source = Path(step_file).expanduser().resolve()
    stat = source.stat()
    source_fingerprint = hashlib.sha256(
        f"{source}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8")
    ).hexdigest()[:16]
    overlay_fingerprint = hashlib.sha256(overlay_id.encode("utf-8")).hexdigest()[:12]
    return overlay_cache_dir() / f"{source.stem}-{source_fingerprint}-{overlay_fingerprint}{suffix}"


def export_step_preview_stl(
    step_file: str,
    linear_deflection: float = 0.5,
    angular_deflection: float = 0.5,
) -> Path:
    source = Path(step_file).expanduser().resolve()
    output = preview_mesh_path(str(source))
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        return output

    shape = read_step(str(source))
    mesh = BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection, True)
    mesh.Perform()

    writer = StlAPI_Writer()
    writer.Write(shape, str(output))
    return output


def export_feature_overlay_stl(
    step_file: str,
    overlay_id: str,
    shapes: list[TopoDS_Shape],
    linear_deflection: float = 0.35,
    angular_deflection: float = 0.4,
) -> list[str]:
    unique_shapes: list[TopoDS_Shape] = []
    for shape in shapes:
        if shape.IsNull():
            continue
        if any(existing.IsSame(shape) for existing in unique_shapes):
            continue
        unique_shapes.append(shape)

    if not unique_shapes:
        return []

    output = overlay_mesh_path(step_file, overlay_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        return [str(output)]

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in unique_shapes:
        builder.Add(compound, shape)

    mesh = BRepMesh_IncrementalMesh(compound, linear_deflection, False, angular_deflection, True)
    mesh.Perform()

    writer = StlAPI_Writer()
    writer.Write(compound, str(output))
    return [str(output)]
