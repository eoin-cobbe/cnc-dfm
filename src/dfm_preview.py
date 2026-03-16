from __future__ import annotations

import hashlib
from pathlib import Path

from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Shape

from dfm_geometry import read_step
from dfm_progress import ProgressReporter


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
    progress: ProgressReporter | None = None,
    percent_start: float = 0.0,
    percent_end: float = 1.0,
) -> Path:
    def stage(percent: float, stage_id: str, label: str, detail: str) -> None:
        if progress is None:
            return
        scaled = percent_start + ((percent_end - percent_start) * percent)
        progress.emit(stage_id=stage_id, label=label, detail=detail, percent=scaled)

    source = Path(step_file).expanduser().resolve()
    output = preview_mesh_path(str(source))
    output.parent.mkdir(parents=True, exist_ok=True)

    stage(0.0, "preview_started", "Generating 3D preview", "Preparing preview output path.")
    if output.exists():
        stage(1.0, "preview_complete", "3D preview ready", "Reused a cached preview mesh.")
        return output

    stage(0.18, "preview_read_step", "Loading geometry for preview", "Reading the STEP file for preview meshing.")
    shape = read_step(str(source))
    stage(0.48, "preview_meshing", "Meshing preview geometry", "Triangulating the shape for the 3D viewer.")
    mesh = BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection, True)
    mesh.Perform()

    stage(0.82, "preview_writing", "Writing preview mesh", "Saving the STL preview artifact.")
    writer = StlAPI_Writer()
    writer.Write(shape, str(output))
    stage(1.0, "preview_complete", "3D preview ready", "Preview mesh is ready for the UI.")
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
