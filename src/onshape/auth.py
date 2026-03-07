from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(_repo_root())
        return True
    except ValueError:
        return False


def auth_config_path() -> Path:
    override = os.getenv("ONSHAPE_AUTH_CONFIG_PATH", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        xdg_root = os.getenv("XDG_CONFIG_HOME", "").strip()
        base = Path(xdg_root).expanduser() if xdg_root else Path.home() / ".config"
        path = base / "cnc-dfm" / "onshape_auth.json"
    if _inside_repo(path):
        raise RuntimeError("Onshape auth config cannot be stored inside the git repository.")
    return path


def load_auth_config() -> Dict[str, str]:
    path = auth_config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        raise RuntimeError(f"Failed to read Onshape auth config at {path}: {exc}") from exc
    return {
        "access_key": str(payload.get("access_key", "")).strip(),
        "secret_key": str(payload.get("secret_key", "")).strip(),
        "base_url": str(payload.get("base_url", "https://cad.onshape.com")).strip().rstrip("/"),
        "auth_mode": str(payload.get("auth_mode", "hmac")).strip().lower() or "hmac",
    }


def save_auth_config(access_key: str, secret_key: str, base_url: str, auth_mode: str) -> Path:
    path = auth_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_key": access_key.strip(),
        "secret_key": secret_key.strip(),
        "base_url": base_url.strip().rstrip("/") or "https://cad.onshape.com",
        "auth_mode": auth_mode.strip().lower() or "hmac",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    os.chmod(path, 0o600)
    return path


def auth_config_summary() -> Dict[str, str]:
    path = auth_config_path()
    env_access = os.getenv("ONSHAPE_ACCESS_KEY", "").strip()
    env_secret = os.getenv("ONSHAPE_SECRET_KEY", "").strip()
    env_base_url = os.getenv("ONSHAPE_BASE_URL", "").strip().rstrip("/")
    env_auth_mode = os.getenv("ONSHAPE_AUTH_MODE", "").strip().lower()
    if env_access and env_secret:
        return {
            "source": "environment",
            "configured": "yes",
            "path": "(env vars)",
            "access_key_masked": _mask_secret(env_access),
            "base_url": env_base_url or "https://cad.onshape.com",
            "auth_mode": env_auth_mode or "hmac",
        }
    payload = load_auth_config()
    if not payload.get("access_key") or not payload.get("secret_key"):
        return {
            "source": "none",
            "configured": "no",
            "path": str(path),
            "access_key_masked": "(not set)",
            "base_url": "https://cad.onshape.com",
            "auth_mode": "hmac",
        }
    return {
        "source": "auth_config_file",
        "configured": "yes",
        "path": str(path),
        "access_key_masked": _mask_secret(payload["access_key"]),
        "base_url": payload["base_url"] or "https://cad.onshape.com",
        "auth_mode": payload["auth_mode"] or "hmac",
    }


def _mask_secret(value: str) -> str:
    stripped = value.strip()
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return f"{stripped[:4]}...{stripped[-4:]}"


@dataclass
class OnshapeCredentials:
    access_key: str
    secret_key: str
    base_url: str
    auth_mode: str = "hmac"

    @classmethod
    def from_env(cls) -> "OnshapeCredentials":
        access_key = os.getenv("ONSHAPE_ACCESS_KEY", "").strip()
        secret_key = os.getenv("ONSHAPE_SECRET_KEY", "").strip()
        base_url = os.getenv("ONSHAPE_BASE_URL", "").strip().rstrip("/")
        auth_mode = os.getenv("ONSHAPE_AUTH_MODE", "").strip().lower()
        if not access_key or not secret_key:
            payload = load_auth_config()
            access_key = access_key or payload.get("access_key", "")
            secret_key = secret_key or payload.get("secret_key", "")
            base_url = base_url or payload.get("base_url", "")
            auth_mode = auth_mode or payload.get("auth_mode", "")
        base_url = base_url or "https://cad.onshape.com"
        auth_mode = auth_mode or "hmac"
        if not access_key or not secret_key:
            raise RuntimeError(
                "Missing Onshape credentials. Set ONSHAPE_ACCESS_KEY/ONSHAPE_SECRET_KEY "
                "or save them with 'run config'."
            )
        if auth_mode not in {"hmac", "basic"}:
            raise RuntimeError("ONSHAPE_AUTH_MODE must be 'hmac' or 'basic'.")
        return cls(access_key=access_key, secret_key=secret_key, base_url=base_url, auth_mode=auth_mode)

    def build_headers(
        self,
        method: str,
        url: str,
        *,
        body: bytes = b"",
        content_type: Optional[str] = None,
        accept: str = "application/json;charset=UTF-8; qs=0.09",
    ) -> Dict[str, str]:
        headers = {"Accept": accept}
        if self.auth_mode == "basic":
            token = _b64(f"{self.access_key}:{self.secret_key}".encode("utf-8"))
            headers["Authorization"] = f"Basic {token}"
            if content_type:
                headers["Content-Type"] = content_type
            return headers

        parsed = urlparse(url)
        path = parsed.path or "/"
        query = parsed.query
        nonce = secrets.token_hex(12)
        date = format_datetime(datetime.now(timezone.utc), usegmt=True)
        content_type_value = content_type or ""
        canonical = (
            f"{method.upper()}\n"
            f"{nonce}\n"
            f"{date}\n"
            f"{content_type_value}\n"
            f"{path}\n"
            f"{query}\n"
        ).lower()
        signature = _b64(hmac.new(self.secret_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest())
        headers.update(
            {
                "Date": date,
                "On-Nonce": nonce,
                "Authorization": f"On {self.access_key}:HmacSHA256:{signature}",
            }
        )
        if content_type:
            headers["Content-Type"] = content_type
        return headers
