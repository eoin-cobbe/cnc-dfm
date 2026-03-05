from __future__ import annotations


def rule_multiplier_from_threshold(
    average_detected: float | None,
    threshold: float | None,
    threshold_kind: str | None,
    slope: float = 0.35,
    max_multiplier: float = 2.0,
) -> float:
    if average_detected is None or threshold is None:
        return 1.0
    if threshold <= 0.0:
        return 1.0
    if threshold_kind == "max":
        severity = max(0.0, (average_detected - threshold) / threshold)
    elif threshold_kind == "min":
        severity = max(0.0, (threshold - average_detected) / threshold)
    else:
        return 1.0
    return min(max_multiplier, 1.0 + (slope * severity))


def rule_multiplier_from_fail_fraction(
    detected_features: int,
    failed_features: int,
    slope: float = 0.4,
    max_multiplier: float = 2.0,
) -> float:
    if detected_features <= 0:
        return 1.0
    frac = max(0.0, min(1.0, failed_features / detected_features))
    return min(max_multiplier, 1.0 + (slope * frac))
