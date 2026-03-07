from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Sequence, Tuple

from dfm_models import FeatureCandidate, OffenderRecord


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _relative_similarity(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1e-6)
    return _clamp01(1.0 - (abs(a - b) / denom))


def _candidate_numeric(candidate: FeatureCandidate) -> float | None:
    value = candidate.meta.get("numeric_value")
    if isinstance(value, (float, int)):
        return float(value)
    return None


def _parameter_label(candidate: FeatureCandidate) -> str:
    return f"{candidate.feature_type}.{(candidate.parameter_id or '').lower()}"


def _bbox_center(box: Dict[str, Any]) -> Tuple[float, float, float] | None:
    try:
        min_corner = box["minCorner"]
        max_corner = box["maxCorner"]
        return (
            (float(min_corner["x"]) + float(max_corner["x"])) * 0.5,
            (float(min_corner["y"]) + float(max_corner["y"])) * 0.5,
            (float(min_corner["z"]) + float(max_corner["z"])) * 0.5,
        )
    except Exception:
        return None


def _distance_similarity(offender: OffenderRecord, box: Dict[str, Any] | None) -> float:
    if not box:
        return 0.0
    center = _bbox_center(box)
    if center is None:
        return 0.0
    try:
        point = offender.occ_anchor["centroid"]
        dx = float(point["x"]) - center[0]
        dy = float(point["y"]) - center[1]
        dz = float(point["z"]) - center[2]
    except Exception:
        return 0.0
    dist = (dx * dx + dy * dy + dz * dz) ** 0.5
    return _clamp01(1.0 - (dist / 50.0))


def _cylinder_similarity(offender: OffenderRecord, cylinders: List[Dict[str, Any]] | None) -> float:
    if not cylinders:
        return 0.0
    candidates = []
    if offender.rule_id == "R1":
        candidates.append(float(offender.current_value))
    if offender.rule_id == "R4":
        candidates.append(float(offender.meta.get("diameter_mm", 0.0)) * 0.5)
    if offender.rule_id == "R6":
        edge_radius = float(offender.meta.get("edge_radius_mm", 0.0))
        if edge_radius > 0.0:
            candidates.append(edge_radius)
    if not candidates:
        return 0.0
    best = 0.0
    for cylinder in cylinders:
        try:
            radius = float(cylinder["radiusMm"])
        except Exception:
            continue
        for target in candidates:
            best = max(best, _relative_similarity(target, radius))
    return best


def _score(offender: OffenderRecord, candidate: FeatureCandidate, traces: Dict[str, Dict[str, Any]]) -> Tuple[float, List[str]]:
    numeric = _candidate_numeric(candidate)
    evidence = list(candidate.evidence)
    raw_trace = traces.get(candidate.feature_id, {})
    fingerprint = raw_trace if isinstance(raw_trace, dict) else {}
    if raw_trace:
        evidence.append("fs-trace")
    if numeric is None:
        evidence.append("non-numeric")
        return 0.0, evidence

    label = _parameter_label(candidate)
    score = 0.0

    if offender.rule_id == "R1" and candidate.feature_type == "fillet" and "radius" in label:
        score = 0.45 + (0.45 * _relative_similarity(offender.current_value, numeric))
    elif offender.rule_id == "R2" and candidate.feature_type == "extrude" and "depth" in label:
        score = 0.45 + (0.45 * _relative_similarity(float(offender.meta.get("depth_mm", 0.0)), numeric))
    elif offender.rule_id == "R4" and candidate.feature_type == "hole":
        if "diameter" in label:
            score = 0.45 + (0.45 * _relative_similarity(float(offender.meta.get("diameter_mm", 0.0)), numeric))
        elif "depth" in label:
            score = 0.45 + (0.45 * _relative_similarity(float(offender.meta.get("depth_mm", 0.0)), numeric))
    elif offender.rule_id == "R6":
        if candidate.feature_type == "extrude" and "depth" in label:
            score = 0.40 + (0.45 * _relative_similarity(float(offender.meta.get("depth_mm", 0.0)), numeric))
        elif candidate.feature_type == "fillet" and "radius" in label:
            score = 0.35 + (0.45 * _relative_similarity(float(offender.meta.get("edge_radius_mm", 0.0)), numeric))
    elif offender.rule_id == "R3":
        score = 0.0

    if fingerprint and score > 0.0:
        score = min(0.99, score + (0.18 * _distance_similarity(offender, fingerprint.get("createdFaceBox"))))
        score = min(0.99, score + (0.12 * _distance_similarity(offender, fingerprint.get("createdBodyBox"))))
        score = min(0.99, score + (0.10 * _cylinder_similarity(offender, fingerprint.get("cylinders"))))
    return score, evidence


def match_offenders_to_candidates(
    offenders: Sequence[OffenderRecord],
    candidates: Sequence[FeatureCandidate],
    traces: Dict[str, Dict[str, Any]],
) -> Dict[int, List[FeatureCandidate]]:
    matches: Dict[int, List[FeatureCandidate]] = {}
    for idx, offender in enumerate(offenders):
        scored: List[FeatureCandidate] = []
        for candidate in candidates:
            score, evidence = _score(offender, candidate, traces)
            if score <= 0.0:
                continue
            scored.append(
                replace(
                    candidate,
                    confidence=score,
                    evidence=evidence,
                    matched_rule_id=offender.rule_id,
                )
            )
        scored.sort(key=lambda row: row.confidence, reverse=True)
        matches[idx] = scored
    return matches


def choose_best_candidates(
    matches: Dict[int, List[FeatureCandidate]],
    *,
    min_confidence: float = 0.65,
    min_margin: float = 0.12,
) -> Dict[int, FeatureCandidate]:
    winners: Dict[int, FeatureCandidate] = {}
    for idx, candidates in matches.items():
        if not candidates:
            continue
        best = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        if best.confidence < min_confidence:
            continue
        if runner_up is not None and (best.confidence - runner_up.confidence) < min_margin:
            continue
        winners[idx] = best
    return winners
