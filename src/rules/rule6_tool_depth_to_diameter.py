from __future__ import annotations

from typing import Dict, Tuple

from OCC.Core.Precision import precision
from OCC.Core.TopoDS import TopoDS_Shape

from dfm_feature_descriptions import average_point, format_mm, format_ratio, nearest_axis_side
from dfm_geometry import shape_bounds
from dfm_models import Config, FeatureInsight, RuleResult
from dfm_scoring import rule_multiplier_from_threshold
from .rule1_internal_corner_radius import detect_internal_corner_features
from .rule2_deep_pocket_ratio import _group_corner_features_by_depth, _split_depth_layer_into_pockets

R6_EDGE_TO_TOOL_RADIUS_FACTOR = 1.3


def evaluate_tool_depth_to_diameter(shape: TopoDS_Shape, cfg: Config) -> RuleResult:
    features_by_axis = detect_internal_corner_features(shape)
    bounds = shape_bounds(shape)
    all_radii = [
        float(feature["radius"])
        for axis_features in features_by_axis.values()
        for feature in axis_features
        if float(feature["radius"]) > precision.Confusion()
    ]
    inferred_min_edge_radius = min(all_radii) if all_radii else None
    inferred_tool_diameter = None
    if inferred_min_edge_radius is not None:
        inferred_tool_diameter = (2.0 * inferred_min_edge_radius) / R6_EDGE_TO_TOOL_RADIUS_FACTOR

    axis_breakdown: Dict[str, Tuple[int, int, int]] = {}
    detected = 0
    offenders = 0
    worst_ratio = 0.0
    ratios = []
    feature_insight_rows = []

    for axis_name, axis_features in features_by_axis.items():
        layers = _group_corner_features_by_depth(axis_features, tol_mm=0.5)
        axis_detected = 0
        axis_offenders = 0
        for layer in layers:
            for pocket_features in _split_depth_layer_into_pockets(layer, axis_name, shape):
                if len(pocket_features) < 2:
                    continue

                depth = max(feature["cylindrical_depth"] for feature in pocket_features)
                if depth <= precision.Confusion():
                    continue

                if inferred_tool_diameter is None or inferred_tool_diameter <= precision.Confusion():
                    continue

                axis_detected += 1
                ratio = depth / inferred_tool_diameter
                ratios.append(ratio)
                worst_ratio = max(worst_ratio, ratio)
                if ratio > cfg.max_tool_depth_to_diameter_ratio:
                    axis_offenders += 1
                    side = nearest_axis_side(
                        average_point(feature["midpoint"] for feature in pocket_features),
                        bounds,
                        axis_name,
                    )
                    feature_insight_rows.append(
                        (
                            ratio,
                            FeatureInsight(
                                summary=(
                                    f"Pocket about {format_mm(depth)} deep on the {side} side would force an inferred "
                                    f"{format_mm(inferred_tool_diameter)} cutter (depth/tool {format_ratio(ratio)})."
                                )
                            ),
                        )
                    )

        axis_pass = max(axis_detected - axis_offenders, 0)
        axis_breakdown[axis_name] = (axis_detected, axis_pass, axis_offenders)
        detected += axis_detected
        offenders += axis_offenders

    pass_count = max(detected - offenders, 0)
    fail_count = offenders
    passed = fail_count == 0
    avg_ratio = (sum(ratios) / len(ratios)) if ratios else 0.0
    rule_mult = rule_multiplier_from_threshold(
        average_detected=avg_ratio,
        threshold=cfg.max_tool_depth_to_diameter_ratio,
        threshold_kind="max",
    )
    details = (
        f"Worst pocket depth/tool diameter ratio is {worst_ratio:.2f}; "
        f"maximum allowed is {cfg.max_tool_depth_to_diameter_ratio:.2f}. "
        f"Using inferred tool diameter {0.0 if inferred_tool_diameter is None else inferred_tool_diameter:.2f} mm "
        f"from minimum detected edge radius {0.0 if inferred_min_edge_radius is None else inferred_min_edge_radius:.2f} mm "
        f"with R_edge = {R6_EDGE_TO_TOOL_RADIUS_FACTOR:.1f} * R_tool. "
        f"Pockets use the same internal-pocket detection as Rule 2."
    )
    if offenders > 0:
        details += f" Found {offenders} likely over-deep pocket feature(s) for the selected tool."

    return RuleResult(
        name="Rule 6 — Tool Depth to Diameter",
        passed=passed,
        summary="PASS" if passed else "FAIL",
        details=details,
        detected_features=detected,
        passed_features=pass_count,
        failed_features=fail_count,
        axis_breakdown=axis_breakdown,
        metric_label="Depth/Tool Ratio",
        average_detected=avg_ratio,
        threshold=cfg.max_tool_depth_to_diameter_ratio,
        threshold_kind="max",
        rule_multiplier=rule_mult,
        feature_insights=[insight for _score, insight in sorted(feature_insight_rows, key=lambda row: row[0], reverse=True)],
    )
