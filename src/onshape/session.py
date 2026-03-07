from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from dfm_models import (
    AnalysisSession,
    FeatureCandidate,
    OffenderRecord,
    OnshapeTarget,
    RemediationProposal,
)


def session_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "cache" / "onshape_sessions"


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def session_path(session_id: str) -> Path:
    return session_root() / f"{session_id}.json"


def save_session(session: AnalysisSession) -> Path:
    root = session_root()
    root.mkdir(parents=True, exist_ok=True)
    path = session_path(session.session_id)
    path.write_text(json.dumps(asdict(session), indent=2) + "\n")
    return path


def _offender(value: Dict[str, Any]) -> OffenderRecord:
    return OffenderRecord(**value)


def _candidate(value: Dict[str, Any]) -> FeatureCandidate:
    return FeatureCandidate(**value)


def _proposal(value: Dict[str, Any]) -> RemediationProposal:
    return RemediationProposal(**value)


def load_session(session_id: str) -> AnalysisSession:
    path = session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Analysis session not found: {session_id}")
    payload = json.loads(path.read_text())
    return AnalysisSession(
        session_id=str(payload["session_id"]),
        target=OnshapeTarget(**payload["target"]),
        source_microversion=str(payload.get("source_microversion", "")),
        export_path=payload.get("export_path"),
        offender_records=[_offender(row) for row in payload.get("offender_records", [])],
        feature_candidates=[_candidate(row) for row in payload.get("feature_candidates", [])],
        proposals=[_proposal(row) for row in payload.get("proposals", [])],
        audit_log=[str(row) for row in payload.get("audit_log", [])],
    )


def append_audit(session: AnalysisSession, line: str) -> None:
    session.audit_log.append(line)
