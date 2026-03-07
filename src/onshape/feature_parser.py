from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from dfm_models import FeatureCandidate

NUMBER_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")

SUPPORTED_TYPES = {
    "fillet": "fillet",
    "edgeblend": "fillet",
    "extrude": "extrude",
    "hole": "hole",
}


def _message(value: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get("message")
    if isinstance(nested, dict):
        return nested
    return value


def _iter_parameters(feature: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for row in feature.get("parameters", []) or []:
        msg = _message(row)
        if msg:
            yield msg


def _parse_numeric_expression(expression: str) -> Optional[float]:
    match = NUMBER_RE.match(expression or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _editable_expression(expression: str) -> bool:
    value = expression.strip()
    if not value:
        return False
    return NUMBER_RE.match(value) is not None


def _supported_feature_type(raw_feature_type: str) -> Optional[str]:
    key = (raw_feature_type or "").strip().lower()
    return SUPPORTED_TYPES.get(key)


def _find_param(parameters: List[Dict[str, Any]], *needles: str) -> Optional[Dict[str, Any]]:
    lowered = [needle.lower() for needle in needles]
    for param in parameters:
        pid = str(param.get("parameterId", "")).lower()
        name = str(param.get("name", "")).lower()
        if any(needle in pid or needle in name for needle in lowered):
            return param
    return None


def _blind_extrude(parameters: List[Dict[str, Any]]) -> bool:
    bound = _find_param(parameters, "endbound", "end type", "endcondition", "depthblind")
    if not bound:
        return True
    value = str(bound.get("value") or bound.get("expression") or "").lower()
    return any(token in value for token in ("blind", "depth", "up_to_next")) or value == ""


def _build_candidate(
    *,
    feature_id: str,
    feature_type: str,
    parameter: Dict[str, Any],
    evidence: List[str],
    target_axis: Optional[str] = None,
) -> Optional[FeatureCandidate]:
    expression = str(parameter.get("expression") or parameter.get("value") or "").strip()
    if not expression:
        return None
    parameter_id = str(parameter.get("parameterId", "")).strip()
    parameter_name = str(parameter.get("name", parameter_id)).strip()
    parsed = _parse_numeric_expression(expression)
    meta = {}
    if parsed is not None:
        meta["numeric_value"] = parsed
    return FeatureCandidate(
        feature_id=feature_id,
        feature_type=feature_type,
        parameter_path=f"parameters.{parameter_id}.expression",
        current_expression=expression,
        editable=_editable_expression(expression),
        confidence=0.0,
        evidence=evidence,
        parameter_id=parameter_id,
        parameter_name=parameter_name or parameter_id,
        target_axis=target_axis,
        meta=meta,
    )


def parse_supported_features(features_payload: Dict[str, Any]) -> List[FeatureCandidate]:
    results: List[FeatureCandidate] = []
    for row in features_payload.get("features", []) or []:
        feature = _message(row)
        feature_type = _supported_feature_type(str(feature.get("featureType", "")))
        if not feature_type:
            continue
        feature_id = str(feature.get("featureId", "")).strip()
        if not feature_id:
            continue
        parameters = list(_iter_parameters(feature))
        evidence = [f"feature:{feature.get('name') or feature_id}", f"type:{feature_type}"]

        if feature_type == "fillet":
            radius = _find_param(parameters, "radius")
            candidate = _build_candidate(
                feature_id=feature_id,
                feature_type=feature_type,
                parameter=radius or {},
                evidence=evidence,
            )
            if candidate:
                results.append(candidate)
            continue

        if feature_type == "extrude":
            if not _blind_extrude(parameters):
                continue
            depth = _find_param(parameters, "depth", "end depth")
            candidate = _build_candidate(
                feature_id=feature_id,
                feature_type=feature_type,
                parameter=depth or {},
                evidence=evidence + ["extrude:blind"],
            )
            if candidate:
                results.append(candidate)
            continue

        if feature_type == "hole":
            diameter = _find_param(parameters, "diameter")
            depth = _find_param(parameters, "depth")
            for parameter, label in ((diameter, "hole:diameter"), (depth, "hole:depth")):
                candidate = _build_candidate(
                    feature_id=feature_id,
                    feature_type=feature_type,
                    parameter=parameter or {},
                    evidence=evidence + [label],
                )
                if candidate:
                    results.append(candidate)
    return results
