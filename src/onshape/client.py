from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dfm_models import OnshapeTarget

from .auth import OnshapeCredentials


class OnshapeError(RuntimeError):
    pass


class OnshapeClient:
    def __init__(self, credentials: OnshapeCredentials, *, api_version: int = 9):
        self.credentials = credentials
        self.base_url = credentials.base_url
        self.api_version = api_version

    @classmethod
    def from_env(cls) -> "OnshapeClient":
        return cls(OnshapeCredentials.from_env())

    def _url(self, path: str, query: Optional[Dict[str, Any]] = None) -> str:
        clean = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{clean}"
        if query:
            encoded = urlencode([(key, value) for key, value in query.items() if value is not None])
            if encoded:
                url = f"{url}?{encoded}"
        return url

    def _request(
        self,
        method: str,
        path_or_url: str,
        *,
        query: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        accept: str = "application/json;charset=UTF-8; qs=0.09",
        timeout: int = 60,
    ) -> Any:
        url = path_or_url if path_or_url.startswith("http") else self._url(path_or_url, query)
        body = b""
        content_type = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            content_type = "application/json"
        headers = self.credentials.build_headers(method, url, body=body, content_type=content_type, accept=accept)
        request = Request(url, data=body or None, method=method.upper(), headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                data = response.read()
                if "application/json" in response.headers.get("Content-Type", ""):
                    return json.loads(data.decode("utf-8"))
                return data
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OnshapeError(f"Onshape API {method.upper()} {url} failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise OnshapeError(f"Onshape API {method.upper()} {url} failed: {exc.reason}") from exc

    def get_features(self, target: OnshapeTarget, *, include_geometry_ids: bool = True) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v{self.api_version}/partstudios/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}/features",
            query={
                "includeGeometryIds": str(include_geometry_ids).lower(),
                "configuration": target.configuration,
            },
        )

    def get_feature(self, target: OnshapeTarget, feature_id: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v{self.api_version}/partstudios/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}/features/featureid/{feature_id}",
            query={"configuration": target.configuration},
        )

    def update_feature(self, target: OnshapeTarget, feature_id: str, feature_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v{self.api_version}/partstudios/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}/features/featureid/{feature_id}",
            query={"configuration": target.configuration},
            payload=feature_payload,
        )

    def get_body_details(self, target: OnshapeTarget) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v{self.api_version}/partstudios/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}/bodydetails",
            query={"configuration": target.configuration},
        )

    def get_elements(self, target: OnshapeTarget) -> Dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v{self.api_version}/documents/d/{target.did}/{target.workspace_type}/{target.wid}/elements",
        )

    def get_parts(self, target: OnshapeTarget) -> Any:
        return self._request(
            "GET",
            f"/api/v{self.api_version}/parts/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}",
            query={"configuration": target.configuration},
        )

    def get_current_microversion(self, target: OnshapeTarget) -> str:
        features = self.get_features(target, include_geometry_ids=False)
        candidates = [
            features.get("sourceMicroversion"),
            features.get("microversionSkew"),
            features.get("serializationVersion"),
        ]
        for candidate in candidates:
            if candidate is not None:
                return str(candidate)
        return ""

    def eval_featurescript(self, target: OnshapeTarget, script: str) -> Dict[str, Any]:
        payload = {"script": script, "libraryVersion": 2500}
        return self._request(
            "POST",
            f"/api/v{self.api_version}/partstudios/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}/featurescript",
            query={"configuration": target.configuration, "rollbackBarIndex": -1},
            payload=payload,
        )

    def create_step_export(self, target: OnshapeTarget) -> Dict[str, Any]:
        payload = {"storeInDocument": True}
        return self._request(
            "POST",
            f"/api/v{self.api_version}/partstudios/d/{target.did}/{target.workspace_type}/{target.wid}/e/{target.eid}/export/step",
            query={"configuration": target.configuration},
            payload=payload,
        )

    def wait_for_translation(self, translation_id: str, *, timeout_s: int = 120, poll_interval_s: float = 2.0) -> Dict[str, Any]:
        deadline = time.time() + timeout_s
        last: Dict[str, Any] = {}
        while time.time() < deadline:
            last = self._request("GET", f"/api/v{self.api_version}/translations/{translation_id}")
            state = str(last.get("requestState", "")).upper()
            if state in {"DONE", "FAILED", "CANCELED"}:
                return last
            time.sleep(poll_interval_s)
        raise OnshapeError(f"Translation {translation_id} did not complete within {timeout_s} seconds.")

    def download_href(self, href: str, destination: Path) -> Path:
        data = self._request("GET", href, accept="application/octet-stream")
        destination.write_bytes(data if isinstance(data, bytes) else bytes(data))
        return destination

    def download_blob_file(self, target: OnshapeTarget, blob_element_id: str, destination: Path) -> Path:
        data = self._request(
            "GET",
            f"/api/v{self.api_version}/blobelements/d/{target.did}/{target.workspace_type}/{target.wid}/e/{blob_element_id}",
            accept="application/octet-stream",
        )
        destination.write_bytes(data if isinstance(data, bytes) else bytes(data))
        return destination
