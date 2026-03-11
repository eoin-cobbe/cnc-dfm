from __future__ import annotations

import hashlib
from pathlib import Path

from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI import StlAPI_Writer

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
