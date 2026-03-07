from __future__ import annotations

from typing import Any, Dict, Iterable, List

from dfm_models import FeatureCandidate, OnshapeTarget

from .client import OnshapeClient


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _unique_features(candidates: Iterable[FeatureCandidate]) -> List[tuple[str, str]]:
    seen = set()
    rows: List[tuple[str, str]] = []
    for candidate in candidates:
        key = (candidate.feature_id, candidate.feature_type)
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
    return rows


def build_batch_feature_trace_script(candidates: List[FeatureCandidate]) -> str:
    features = _unique_features(candidates)
    feature_rows = ",\n        ".join(
        f'fingerprint("{_escape(feature_id)}", "{_escape(feature_type)}")' for feature_id, feature_type in features
    )
    if not feature_rows:
        feature_rows = ""
    return f"""
function(context is Context, queries)
{{
    function mmPoint(p is Vector) returns map
    {{
        return {{
            "x" : p[0] / millimeter,
            "y" : p[1] / millimeter,
            "z" : p[2] / millimeter
        }};
    }}

    function dirPoint(v is Vector) returns map
    {{
        return {{
            "x" : v[0],
            "y" : v[1],
            "z" : v[2]
        }};
    }}

    function bboxFor(topologyQuery is Query) returns map
    {{
        const entities = evaluateQuery(context, topologyQuery);
        if (size(entities) == 0)
            return {{}};
        const box = evBox3d(context, {{
                "topology" : topologyQuery,
                "tight" : true
        }});
        return {{
            "minCorner" : mmPoint(box.minCorner),
            "maxCorner" : mmPoint(box.maxCorner)
        }};
    }}

    function cylinderRows(faceQuery is Query) returns array
    {{
        var rows = [];
        for (var face in evaluateQuery(context, faceQuery))
        {{
            const surface = evSurfaceDefinition(context, {{
                    "face" : face
            }});
            if (surface.surfaceType != SurfaceType.CYLINDER)
                continue;
            rows = append(rows, {{
                    "radiusMm" : surface.radius / millimeter,
                    "axisOriginMm" : mmPoint(surface.coordSystem.origin),
                    "axisDirection" : dirPoint(surface.coordSystem.zAxis)
            }});
        }}
        return rows;
    }}

    function fingerprint(featureId is string, featureType is string)
    {{
        const featureToken = makeId(featureId);
        const createdFaces = qCreatedBy(featureToken, EntityType.FACE);
        const createdBodies = qCreatedBy(featureToken, EntityType.BODY);
        return {{
            "featureId" : featureId,
            "featureType" : featureType,
            "createdFaceCount" : size(evaluateQuery(context, createdFaces)),
            "createdBodyCount" : size(evaluateQuery(context, createdBodies)),
            "createdFaceQueries" : transientQueriesToStrings(evaluateQuery(context, createdFaces)),
            "createdBodyQueries" : transientQueriesToStrings(evaluateQuery(context, createdBodies)),
            "createdFaceBox" : bboxFor(createdFaces),
            "createdBodyBox" : bboxFor(createdBodies),
            "cylinders" : cylinderRows(createdFaces)
        }};
    }}

    return {{
        "features" : [
        {feature_rows}
        ]
    }};
}}
""".strip()


def _collect_feature_rows(value: Any, sink: List[Dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if "featureId" in value and "featureType" in value:
            sink.append(value)
        for item in value.values():
            _collect_feature_rows(item, sink)
        return
    if isinstance(value, list):
        for item in value:
            _collect_feature_rows(item, sink)


def extract_feature_fingerprints(fs_response: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    _collect_feature_rows(fs_response, rows)
    fingerprints: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        feature_id = str(row.get("featureId", "")).strip()
        if not feature_id:
            continue
        fingerprints[feature_id] = row
    return fingerprints


def collect_feature_fingerprints(
    client: OnshapeClient,
    target: OnshapeTarget,
    candidates: List[FeatureCandidate],
) -> Dict[str, Dict[str, Any]]:
    if not candidates:
        return {}
    try:
        response = client.eval_featurescript(target, build_batch_feature_trace_script(candidates))
    except Exception:
        return {}
    return extract_feature_fingerprints(response)
