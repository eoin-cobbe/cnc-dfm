from __future__ import annotations

import tempfile
from pathlib import Path
import zipfile

from dfm_models import OnshapeTarget

from .client import OnshapeClient, OnshapeError


def _finalize_step_download(path: Path) -> Path:
    if not zipfile.is_zipfile(path):
        return path
    with zipfile.ZipFile(path) as archive:
        step_members = [
            name for name in archive.namelist() if name.lower().endswith(".step") or name.lower().endswith(".stp")
        ]
        if not step_members:
            raise OnshapeError(f"Downloaded export archive did not contain a STEP file: {path}")
        member = step_members[0]
        output_path = path.with_name("part.step")
        if output_path == path:
            output_path = path.with_name("part_extracted.step")
        with archive.open(member) as source, output_path.open("wb") as dest:
            dest.write(source.read())
    return output_path


def export_partstudio_step(client: OnshapeClient, target: OnshapeTarget, *, prefix: str = "onshape-") -> Path:
    created = client.create_step_export(target)
    translation_id = created.get("id") or created.get("translationId")
    if not translation_id:
        raise OnshapeError(f"Unexpected STEP export response: {created}")
    finished = client.wait_for_translation(str(translation_id))
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    output_path = temp_dir / "part.download"
    result_element_ids = finished.get("resultElementIds")
    if isinstance(result_element_ids, list) and result_element_ids:
        downloaded = client.download_blob_file(target, str(result_element_ids[0]), output_path)
        return _finalize_step_download(downloaded)
    href = finished.get("resultExternalDataUrl") or finished.get("href")
    if href:
        downloaded = client.download_href(str(href), output_path)
        return _finalize_step_download(downloaded)
    raise OnshapeError(f"STEP export completed without a downloadable result: {finished}")
