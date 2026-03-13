from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dfm_app_api import _config_to_model
from dfm_check import analyze_step_file
from dfm_config import config_path, load_config, load_saved_only, normalize_config_payload, save_config_payload
from dfm_materials import MATERIAL_OPTIONS
from dfm_preview import export_step_preview_stl, overlay_cache_dir, preview_cache_dir


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def web_upload_cache_dir() -> Path:
    return repo_root() / "cache" / "web" / "uploads"


def ensure_runtime_dirs() -> None:
    preview_cache_dir().mkdir(parents=True, exist_ok=True)
    overlay_cache_dir().mkdir(parents=True, exist_ok=True)
    web_upload_cache_dir().mkdir(parents=True, exist_ok=True)


def sanitize_filename(name: str) -> str:
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem or "part"
    safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip("-._") or "part"
    if suffix not in {".step", ".stp"}:
        suffix = ".step"
    return f"{safe_stem}{suffix}"


def parse_origins() -> list[str]:
    raw = os.getenv("CNC_DFM_WEB_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [value.strip() for value in raw.split(",") if value.strip()]


def store_upload(upload: UploadFile) -> Path:
    ensure_runtime_dirs()
    target_name = f"{secrets.token_hex(8)}-{sanitize_filename(upload.filename or 'part.step')}"
    target_path = web_upload_cache_dir() / target_name
    with target_path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return target_path


def artifact_url_for_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    preview_root = preview_cache_dir().resolve()
    overlay_root = overlay_cache_dir().resolve()

    if resolved.is_relative_to(preview_root):
        return f"/artifacts/previews/{resolved.name}"
    if resolved.is_relative_to(overlay_root):
        return f"/artifacts/feature-overlays/{resolved.name}"
    raise ValueError(f"Unsupported artifact path: {resolved}")


def rewrite_overlay_mesh_paths(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: rewrite_overlay_mesh_paths(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [rewrite_overlay_mesh_paths(value) for value in payload]
    if isinstance(payload, str) and payload.endswith(".stl"):
        candidate = Path(payload)
        if candidate.exists():
            try:
                return artifact_url_for_path(candidate)
            except ValueError:
                return payload
    return payload


def error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"message": message}})


ensure_runtime_dirs()

app = FastAPI(
    title="cnc-dfm web api",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins() or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts/previews", StaticFiles(directory=str(preview_cache_dir())), name="preview-artifacts")
app.mount(
    "/artifacts/feature-overlays",
    StaticFiles(directory=str(overlay_cache_dir())),
    name="feature-overlay-artifacts",
)


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "name": "cnc-dfm web api",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
def health() -> Dict[str, Any]:
    analysis_runtime = {"available": True}
    try:
        import dfm_check  # noqa: F401
    except Exception as exc:
        analysis_runtime = {
            "available": False,
            "errorType": exc.__class__.__name__,
            "message": str(exc),
        }

    return {
        "status": "ok",
        "apiVersion": 1,
        "configPath": str(config_path()),
        "configExists": config_path().exists(),
        "pythonExecutable": sys.executable,
        "platform": os.sys.platform,
        "cwd": os.getcwd(),
        "analysisRuntime": analysis_runtime,
        "webApi": {
            "origins": parse_origins(),
            "previewBaseUrl": "/artifacts/previews",
            "overlayBaseUrl": "/artifacts/feature-overlays",
        },
    }


@app.get("/api/v1/materials")
def materials() -> Dict[str, Any]:
    return {
        "materials": [asdict(material) for material in MATERIAL_OPTIONS],
    }


@app.get("/api/v1/config")
def config_show() -> Dict[str, Any]:
    saved = load_saved_only()
    effective = load_config()
    return {
        "configPath": str(config_path()),
        "hasSavedConfig": saved is not None,
        "values": effective,
    }


@app.put("/api/v1/config")
def config_save(payload: Dict[str, Any]) -> Dict[str, Any]:
    saved = save_config_payload(payload, base=load_config())
    return {
        "configPath": str(config_path()),
        "hasSavedConfig": True,
        "values": saved,
    }


@app.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    qty: int = Form(1),
    config_json: str | None = Form(None),
    save_config: bool = Form(False),
    generate_preview: bool = Form(True),
) -> Dict[str, Any]:
    if qty < 1:
        raise HTTPException(status_code=400, detail="qty must be >= 1")

    if not file.filename:
        raise HTTPException(status_code=400, detail="A STEP file is required.")

    upload_path = store_upload(file)
    cfg_values = load_config()

    if config_json:
        payload = json.loads(config_json)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="config_json must decode to an object")
        if save_config:
            cfg_values = save_config_payload(payload, base=cfg_values)
        else:
            cfg_values = normalize_config_payload(payload, base=cfg_values)

    analysis = analyze_step_file(str(upload_path), _config_to_model(cfg_values), qty)
    analysis_payload = rewrite_overlay_mesh_paths(asdict(analysis))
    analysis_payload["file_path"] = file.filename

    preview_url = None
    if generate_preview:
        preview_path = export_step_preview_stl(str(upload_path))
        preview_url = artifact_url_for_path(preview_path)

    return {
        "analysis": analysis_payload,
        "previewUrl": preview_url,
        "uploadedFileName": file.filename,
        "config": cfg_values,
    }


@app.exception_handler(json.JSONDecodeError)
async def handle_json_decode_error(_request: Any, exc: json.JSONDecodeError) -> JSONResponse:
    return error_response(f"Invalid JSON payload: {exc.msg}")


@app.exception_handler(Exception)
async def handle_generic_error(_request: Any, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail}})
    return error_response(str(exc), status_code=500)
