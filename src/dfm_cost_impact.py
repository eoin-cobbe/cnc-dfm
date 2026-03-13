from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
import re
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from dfm_models import Config, CostImpactBreakdown, CostImpactRange, FeatureInsight, PartProcessData, Recommendation, RuleResult
from dfm_scoring import rule_multiplier_from_fail_fraction, rule_multiplier_from_threshold


R1_ABSOLUTE_PASS_RADIUS_MM = 0.8
R1_NEAR_MIN_RADIUS_MM = 2.0
R1_MAX_MULTIPLIER = 5.0


@dataclass(frozen=True)
class _CostSnapshot:
    unit_cost_eur: float
    batch_cost_eur: float
    base_machining_time_min: float
    machine_hourly_rate_eur: float
    rule_multiplier: float
    hole_count_multiplier: float
    radius_count_multiplier: float


@dataclass(frozen=True)
class _ScenarioResult:
    label: str
    direct_snapshot: _CostSnapshot
    final_snapshot: _CostSnapshot


def recompute_cost_snapshot(
    process_data: PartProcessData,
    *,
    rule_multiplier: Optional[float] = None,
    hole_count_multiplier: Optional[float] = None,
    radius_count_multiplier: Optional[float] = None,
    machine_hourly_rate_eur: Optional[float] = None,
) -> _CostSnapshot:
    next_rule_multiplier = process_data.rule_multiplier if rule_multiplier is None else rule_multiplier
    next_hole_multiplier = process_data.hole_count_multiplier if hole_count_multiplier is None else hole_count_multiplier
    next_radius_multiplier = process_data.radius_count_multiplier if radius_count_multiplier is None else radius_count_multiplier
    next_machine_rate = process_data.machine_hourly_rate_eur if machine_hourly_rate_eur is None else machine_hourly_rate_eur

    base_machining_time_min = (
        process_data.roughing_time_min
        * process_data.surface_area_multiplier
        * process_data.complexity_multiplier
        * next_rule_multiplier
        * next_hole_multiplier
        * next_radius_multiplier
    )
    base_machining_cost = (base_machining_time_min / 60.0) * next_machine_rate
    unit_cost_eur = (process_data.material_stock_cost_eur + base_machining_cost) * process_data.qty_multiplier
    batch_cost_eur = unit_cost_eur * float(process_data.qty)
    return _CostSnapshot(
        unit_cost_eur=unit_cost_eur,
        batch_cost_eur=batch_cost_eur,
        base_machining_time_min=base_machining_time_min,
        machine_hourly_rate_eur=next_machine_rate,
        rule_multiplier=next_rule_multiplier,
        hole_count_multiplier=next_hole_multiplier,
        radius_count_multiplier=next_radius_multiplier,
    )


def _unit_baseline_process_data(process_data: PartProcessData) -> PartProcessData:
    return replace(
        process_data,
        qty=1,
        qty_multiplier=1.0,
    )


def attach_cost_impacts(
    recommendations: List[Recommendation],
    rules: Sequence[RuleResult],
    process_data: PartProcessData,
    cfg: Config,
) -> None:
    rules_by_key = {_rule_key(rule.name): rule for rule in rules if _rule_key(rule.name) is not None}
    baseline_process_data = _unit_baseline_process_data(process_data)
    baseline = recompute_cost_snapshot(baseline_process_data)
    for recommendation in recommendations:
        recommendation.cost_impact = estimate_recommendation_cost_impact(
            recommendation,
            rules_by_key=rules_by_key,
            process_data=baseline_process_data,
            cfg=cfg,
            baseline=baseline,
        )


def estimate_recommendation_cost_impact(
    recommendation: Recommendation,
    *,
    rules_by_key: Dict[str, RuleResult],
    process_data: PartProcessData,
    cfg: Config,
    baseline: Optional[_CostSnapshot] = None,
) -> Optional[CostImpactRange]:
    baseline_snapshot = baseline or recompute_cost_snapshot(process_data)
    key = _recommendation_key(recommendation)
    if key is None:
        return None

    if key == "rule0":
        rule = rules_by_key.get("rule0")
        if rule is None or rule.failed_features <= 0:
            return None
        return _rule0_impact(recommendation, rule, process_data, baseline_snapshot)
    if key == "rule1":
        rule = rules_by_key.get("rule1")
        if rule is None:
            return None
        return _rule1_impact(recommendation, rule, process_data, cfg, baseline_snapshot)
    if key in {"rule2", "rule3", "rule4", "rule6"}:
        rule = rules_by_key.get(key)
        if rule is None:
            return None
        return _threshold_rule_impact(recommendation, rule, process_data, cfg, baseline_snapshot)
    if key == "rule5":
        rule = rules_by_key.get("rule5")
        if rule is None:
            return None
        return _rule5_impact(recommendation, rule, process_data, cfg, baseline_snapshot)
    if key == "process":
        rule = rules_by_key.get("rule5")
        if rule is None:
            return None
        return _process_machine_impact(recommendation, rule, process_data, cfg, baseline_snapshot)
    if key == "hole_count":
        return _count_multiplier_impact(
            recommendation,
            process_data=process_data,
            baseline=baseline_snapshot,
            count=process_data.hole_count,
            current_multiplier=process_data.hole_count_multiplier,
            per_feature_penalty=cfg.hole_count_penalty_per_feature,
            max_multiplier=cfg.hole_count_penalty_max_multiplier,
            label="Hole-count multiplier",
            count_label="hole feature",
            update_attr="hole",
        )
    if key == "radius_count":
        return _count_multiplier_impact(
            recommendation,
            process_data=process_data,
            baseline=baseline_snapshot,
            count=process_data.radius_count,
            current_multiplier=process_data.radius_count_multiplier,
            per_feature_penalty=cfg.radius_count_penalty_per_feature,
            max_multiplier=cfg.radius_count_penalty_max_multiplier,
            label="Radius-count multiplier",
            count_label="internal corner feature",
            update_attr="radius",
        )
    return None


def _recommendation_key(recommendation: Recommendation) -> Optional[str]:
    source_key = _rule_key(recommendation.source)
    if source_key is not None:
        return source_key
    if recommendation.source == "Hole count":
        return "hole_count"
    if recommendation.source == "Radius count":
        return "radius_count"
    if recommendation.source == "Process":
        return "process"
    return None


def _rule_key(text: str) -> Optional[str]:
    match = re.search(r"Rule\s+(\d+)", text)
    if match is None:
        return None
    return f"rule{match.group(1)}"


def _combine_rule_multiplier(process_data: PartProcessData, current_rule_multiplier: float, next_rule_multiplier: float) -> float:
    safe_current = max(current_rule_multiplier, 1e-9)
    return process_data.rule_multiplier / safe_current * next_rule_multiplier


def _savings(baseline_value: float, scenario_value: float) -> float:
    return max(0.0, baseline_value - scenario_value)


def _make_breakdown(
    label: str,
    conservative_savings_unit: float,
    optimistic_savings_unit: float,
    conservative_savings_batch: float,
    optimistic_savings_batch: float,
    details: str,
) -> CostImpactBreakdown:
    return CostImpactBreakdown(
        label=label,
        minimum_unit_savings_eur=min(conservative_savings_unit, optimistic_savings_unit),
        maximum_unit_savings_eur=max(conservative_savings_unit, optimistic_savings_unit),
        minimum_batch_savings_eur=min(conservative_savings_batch, optimistic_savings_batch),
        maximum_batch_savings_eur=max(conservative_savings_batch, optimistic_savings_batch),
        details=details,
    )


def _build_cost_impact(
    baseline: _CostSnapshot,
    conservative: _ScenarioResult,
    optimistic: _ScenarioResult,
    rationale: str,
    direct_breakdown: List[CostImpactBreakdown],
    linked_breakdown: List[CostImpactBreakdown],
) -> Optional[CostImpactRange]:
    conservative_unit_savings = _savings(baseline.unit_cost_eur, conservative.final_snapshot.unit_cost_eur)
    optimistic_unit_savings = _savings(baseline.unit_cost_eur, optimistic.final_snapshot.unit_cost_eur)
    conservative_batch_savings = _savings(baseline.batch_cost_eur, conservative.final_snapshot.batch_cost_eur)
    optimistic_batch_savings = _savings(baseline.batch_cost_eur, optimistic.final_snapshot.batch_cost_eur)
    maximum_unit_savings = max(conservative_unit_savings, optimistic_unit_savings)
    maximum_batch_savings = max(conservative_batch_savings, optimistic_batch_savings)
    if maximum_unit_savings <= 1e-9 and maximum_batch_savings <= 1e-9:
        return None

    minimum_unit_savings = min(conservative_unit_savings, optimistic_unit_savings)
    minimum_batch_savings = min(conservative_batch_savings, optimistic_batch_savings)
    current_unit_cost = baseline.unit_cost_eur
    min_percent = (minimum_unit_savings / current_unit_cost * 100.0) if current_unit_cost > 0.0 else 0.0
    max_percent = (maximum_unit_savings / current_unit_cost * 100.0) if current_unit_cost > 0.0 else 0.0
    return CostImpactRange(
        current_unit_cost_eur=current_unit_cost,
        current_batch_cost_eur=baseline.batch_cost_eur,
        minimum_unit_savings_eur=minimum_unit_savings,
        maximum_unit_savings_eur=maximum_unit_savings,
        minimum_batch_savings_eur=minimum_batch_savings,
        maximum_batch_savings_eur=maximum_batch_savings,
        minimum_percent_savings=min_percent,
        maximum_percent_savings=max_percent,
        conservative_label=conservative.label,
        optimistic_label=optimistic.label,
        rationale=rationale,
        direct_breakdown=direct_breakdown,
        linked_breakdown=linked_breakdown,
    )


def _clone_values(insights: Iterable[FeatureInsight]) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for insight in insights:
        if insight.measured_value is None:
            continue
        values[insight.id] = float(insight.measured_value)
    return values


def _override_values(values: Dict[str, float], overrides: Dict[str, float]) -> List[float]:
    next_values = dict(values)
    next_values.update(overrides)
    return list(next_values.values())


def _rule1_multiplier(values: Sequence[float], recommended_target: float) -> float:
    if not values:
        return 1.0
    average_radius = sum(values) / len(values)
    rule_multiplier = rule_multiplier_from_threshold(
        average_detected=average_radius,
        threshold=recommended_target,
        threshold_kind="min",
        slope=1.25,
        max_multiplier=R1_MAX_MULTIPLIER,
    )
    fail_count = sum(1 for value in values if value < R1_ABSOLUTE_PASS_RADIUS_MM)
    near_min_count = sum(1 for value in values if value < R1_NEAR_MIN_RADIUS_MM)
    if fail_count > 0:
        fail_fraction = fail_count / len(values)
        rule_multiplier = min(R1_MAX_MULTIPLIER, max(rule_multiplier, 1.0 + (4.0 * fail_fraction)))
    if near_min_count > 0:
        near_min_fraction = near_min_count / len(values)
        rule_multiplier = min(R1_MAX_MULTIPLIER, max(rule_multiplier, 1.0 + (2.5 * near_min_fraction)))
    return rule_multiplier


def _threshold_rule_multiplier(rule: RuleResult, values: Sequence[float]) -> float:
    average_detected = (sum(values) / len(values)) if values else 0.0
    return rule_multiplier_from_threshold(
        average_detected=average_detected,
        threshold=rule.threshold,
        threshold_kind=rule.threshold_kind,
    )


def _best_feature(
    recommendation: Recommendation,
    calculator: Callable[[FeatureInsight], Optional[CostImpactRange]],
) -> Optional[tuple[FeatureInsight, CostImpactRange]]:
    best: Optional[tuple[FeatureInsight, CostImpactRange]] = None
    for insight in recommendation.feature_insights:
        impact = calculator(insight)
        insight.cost_impact = impact
        if impact is None:
            continue
        if best is None or impact.maximum_unit_savings_eur > best[1].maximum_unit_savings_eur:
            best = (insight, impact)
    return best


def _rule0_impact(
    recommendation: Recommendation,
    rule: RuleResult,
    process_data: PartProcessData,
    baseline: _CostSnapshot,
) -> Optional[CostImpactRange]:
    total_failures = rule.failed_features
    baseline_rule_multiplier = rule.rule_multiplier

    def scenario_for_fixed_count(fixed_count: int, label: str) -> _ScenarioResult:
        next_rule_multiplier = rule_multiplier_from_fail_fraction(
            detected_features=total_failures,
            failed_features=max(0, total_failures - fixed_count),
        )
        combined_rule_multiplier = _combine_rule_multiplier(process_data, baseline_rule_multiplier, next_rule_multiplier)
        snapshot = recompute_cost_snapshot(process_data, rule_multiplier=combined_rule_multiplier)
        return _ScenarioResult(label=label, direct_snapshot=snapshot, final_snapshot=snapshot)

    def per_feature_impact(_insight: FeatureInsight) -> Optional[CostImpactRange]:
        scenario = scenario_for_fixed_count(1, "Add relief to this corner")
        direct = _make_breakdown(
            "Rule 0 multiplier",
            _savings(baseline.unit_cost_eur, scenario.direct_snapshot.unit_cost_eur),
            _savings(baseline.unit_cost_eur, scenario.direct_snapshot.unit_cost_eur),
            _savings(baseline.batch_cost_eur, scenario.direct_snapshot.batch_cost_eur),
            _savings(baseline.batch_cost_eur, scenario.direct_snapshot.batch_cost_eur),
            f"{baseline_rule_multiplier:.2f}x -> {rule_multiplier_from_fail_fraction(detected_features=total_failures, failed_features=max(0, total_failures - 1)):.2f}x",
        )
        return _build_cost_impact(
            baseline,
            scenario,
            scenario,
            "Each relieved sharp closed corner removes one Rule 0 failure from the current cost model.",
            [direct],
            [],
        )

    best = _best_feature(recommendation, per_feature_impact)
    conservative = scenario_for_fixed_count(1, "Relieve the single most expensive corner")
    optimistic = scenario_for_fixed_count(total_failures, "Relieve every flagged corner")
    direct_breakdown = [
        _make_breakdown(
            "Rule 0 multiplier",
            _savings(baseline.unit_cost_eur, conservative.direct_snapshot.unit_cost_eur),
            _savings(baseline.unit_cost_eur, optimistic.direct_snapshot.unit_cost_eur),
            _savings(baseline.batch_cost_eur, conservative.direct_snapshot.batch_cost_eur),
            _savings(baseline.batch_cost_eur, optimistic.direct_snapshot.batch_cost_eur),
            f"{baseline_rule_multiplier:.2f}x -> {conservative.direct_snapshot.rule_multiplier:.2f}x to {optimistic.direct_snapshot.rule_multiplier:.2f}x",
        )
    ]
    if best is not None:
        conservative = _ScenarioResult(best[1].conservative_label, conservative.direct_snapshot, conservative.final_snapshot)
    return _build_cost_impact(
        baseline,
        conservative,
        optimistic,
        "Savings come from reducing the Rule 0 fail-fraction multiplier in the current machining-cost model.",
        direct_breakdown,
        [],
    )


def _rule1_impact(
    recommendation: Recommendation,
    rule: RuleResult,
    process_data: PartProcessData,
    cfg: Config,
    baseline: _CostSnapshot,
) -> Optional[CostImpactRange]:
    all_insights = list(rule.all_feature_insights or rule.feature_insights)
    if not all_insights:
        return None
    all_values = _clone_values(all_insights)
    implicated_ids = [insight.id for insight in recommendation.feature_insights if insight.id in all_values]
    if not implicated_ids:
        return None
    baseline_rule_multiplier = rule.rule_multiplier

    def scenario_values(overrides: Dict[str, float]) -> tuple[float, _CostSnapshot]:
        next_rule_multiplier = _rule1_multiplier(_override_values(all_values, overrides), cfg.min_internal_corner_radius_mm)
        combined_rule_multiplier = _combine_rule_multiplier(process_data, baseline_rule_multiplier, next_rule_multiplier)
        return next_rule_multiplier, recompute_cost_snapshot(process_data, rule_multiplier=combined_rule_multiplier)

    def feature_impact(insight: FeatureInsight) -> Optional[CostImpactRange]:
        if insight.measured_value is None:
            return None
        conservative_rule_multiplier, conservative_snapshot = scenario_values(
            {insight.id: max(float(insight.measured_value), R1_ABSOLUTE_PASS_RADIUS_MM)}
        )
        optimistic_rule_multiplier, optimistic_snapshot = scenario_values(
            {insight.id: max(float(insight.measured_value), cfg.min_internal_corner_radius_mm)}
        )
        conservative = _ScenarioResult("Increase this radius to the pass floor", conservative_snapshot, conservative_snapshot)
        optimistic = _ScenarioResult("Increase this radius to the design target", optimistic_snapshot, optimistic_snapshot)
        direct_breakdown = [
            _make_breakdown(
                "Rule 1 multiplier",
                _savings(baseline.unit_cost_eur, conservative_snapshot.unit_cost_eur),
                _savings(baseline.unit_cost_eur, optimistic_snapshot.unit_cost_eur),
                _savings(baseline.batch_cost_eur, conservative_snapshot.batch_cost_eur),
                _savings(baseline.batch_cost_eur, optimistic_snapshot.batch_cost_eur),
                f"{baseline_rule_multiplier:.2f}x -> {conservative_rule_multiplier:.2f}x to {optimistic_rule_multiplier:.2f}x",
            )
        ]
        return _build_cost_impact(
            baseline,
            conservative,
            optimistic,
            "Rule 1 savings come from increasing one radius enough to reduce fail-fraction and near-min penalty pressure in the current model.",
            direct_breakdown,
            [],
        )

    best = _best_feature(recommendation, feature_impact)
    if best is None:
        return None
    conservative_rule_multiplier, conservative_snapshot = scenario_values(
        {best[0].id: max(float(best[0].measured_value or 0.0), R1_ABSOLUTE_PASS_RADIUS_MM)}
    )
    optimistic_rule_multiplier, optimistic_snapshot = scenario_values(
        {insight_id: cfg.min_internal_corner_radius_mm for insight_id in implicated_ids}
    )
    conservative = _ScenarioResult("Increase the worst radius to the pass floor", conservative_snapshot, conservative_snapshot)
    optimistic = _ScenarioResult("Increase every flagged radius to the design target", optimistic_snapshot, optimistic_snapshot)
    direct_breakdown = [
        _make_breakdown(
            "Rule 1 multiplier",
            _savings(baseline.unit_cost_eur, conservative_snapshot.unit_cost_eur),
            _savings(baseline.unit_cost_eur, optimistic_snapshot.unit_cost_eur),
            _savings(baseline.batch_cost_eur, conservative_snapshot.batch_cost_eur),
            _savings(baseline.batch_cost_eur, optimistic_snapshot.batch_cost_eur),
            f"{baseline_rule_multiplier:.2f}x -> {conservative_rule_multiplier:.2f}x to {optimistic_rule_multiplier:.2f}x",
        )
    ]
    return _build_cost_impact(
        baseline,
        conservative,
        optimistic,
        "Savings come from re-evaluating the current Rule 1 multiplier after raising the implicated internal corner radii.",
        direct_breakdown,
        [],
    )


def _threshold_rule_impact(
    recommendation: Recommendation,
    rule: RuleResult,
    process_data: PartProcessData,
    cfg: Config,
    baseline: _CostSnapshot,
) -> Optional[CostImpactRange]:
    all_insights = list(rule.all_feature_insights or rule.feature_insights)
    if not all_insights or rule.threshold is None:
        return None
    all_values = _clone_values(all_insights)
    implicated_ids = [insight.id for insight in recommendation.feature_insights if insight.id in all_values]
    if not implicated_ids:
        return None
    baseline_rule_multiplier = rule.rule_multiplier

    def scenario_values(overrides: Dict[str, float]) -> tuple[float, _CostSnapshot]:
        next_rule_multiplier = _threshold_rule_multiplier(rule, _override_values(all_values, overrides))
        combined_rule_multiplier = _combine_rule_multiplier(process_data, baseline_rule_multiplier, next_rule_multiplier)
        return next_rule_multiplier, recompute_cost_snapshot(process_data, rule_multiplier=combined_rule_multiplier)

    def feature_impact(insight: FeatureInsight) -> Optional[CostImpactRange]:
        if insight.measured_value is None:
            return None
        target = float(rule.threshold)
        next_value = target if rule.threshold_kind == "max" else max(target, float(insight.measured_value))
        next_rule_multiplier, snapshot = scenario_values({insight.id: next_value})
        scenario = _ScenarioResult("Fix this feature to the modeled threshold", snapshot, snapshot)
        direct_breakdown = [
            _make_breakdown(
                f"{rule.name.split(' — ')[0]} multiplier",
                _savings(baseline.unit_cost_eur, snapshot.unit_cost_eur),
                _savings(baseline.unit_cost_eur, snapshot.unit_cost_eur),
                _savings(baseline.batch_cost_eur, snapshot.batch_cost_eur),
                _savings(baseline.batch_cost_eur, snapshot.batch_cost_eur),
                f"{baseline_rule_multiplier:.2f}x -> {next_rule_multiplier:.2f}x",
            )
        ]
        return _build_cost_impact(
            baseline,
            scenario,
            scenario,
            "This estimate comes from re-running the current rule multiplier after fixing one flagged feature to the rule threshold.",
            direct_breakdown,
            [],
        )

    best = _best_feature(recommendation, feature_impact)
    if best is None:
        return None
    conservative_rule_multiplier, conservative_snapshot = scenario_values({best[0].id: float(rule.threshold)})
    optimistic_rule_multiplier, optimistic_snapshot = scenario_values({insight_id: float(rule.threshold) for insight_id in implicated_ids})
    conservative = _ScenarioResult("Fix the single worst flagged feature", conservative_snapshot, conservative_snapshot)
    optimistic = _ScenarioResult("Fix every flagged feature to the modeled threshold", optimistic_snapshot, optimistic_snapshot)
    direct_breakdown = [
        _make_breakdown(
            f"{rule.name.split(' — ')[0]} multiplier",
            _savings(baseline.unit_cost_eur, conservative_snapshot.unit_cost_eur),
            _savings(baseline.unit_cost_eur, optimistic_snapshot.unit_cost_eur),
            _savings(baseline.batch_cost_eur, conservative_snapshot.batch_cost_eur),
            _savings(baseline.batch_cost_eur, optimistic_snapshot.batch_cost_eur),
            f"{baseline_rule_multiplier:.2f}x -> {conservative_rule_multiplier:.2f}x to {optimistic_rule_multiplier:.2f}x",
        )
    ]
    return _build_cost_impact(
        baseline,
        conservative,
        optimistic,
        "Savings come from reducing the affected rule multiplier inside the existing machining-cost formula.",
        direct_breakdown,
        [],
    )


def _parse_setup_keys(feature_insights: Iterable[FeatureInsight]) -> List[str]:
    setup_keys: List[str] = []
    for insight in feature_insights:
        match = re.search(r"requiring the\s+([XYZ][+-])\s+setup direction", insight.summary)
        if match is None:
            continue
        setup_key = match.group(1)
        if setup_key not in setup_keys:
            setup_keys.append(setup_key)
    return setup_keys


def _is_flip_only(setup_keys: Sequence[str]) -> bool:
    if len(setup_keys) <= 1:
        return True
    if len(setup_keys) != 2:
        return False
    axes = {key[0] for key in setup_keys}
    signs = {key[1] for key in setup_keys}
    return len(axes) == 1 and signs == {"+", "-"}


def _setup_rule_multiplier(setups: int, cfg: Config) -> float:
    return rule_multiplier_from_threshold(
        average_detected=float(setups),
        threshold=float(cfg.max_setups),
        threshold_kind="max",
    )


def _evaluate_setup_scenario(
    remaining_setup_keys: Sequence[str],
    rule: RuleResult,
    process_data: PartProcessData,
    cfg: Config,
) -> _ScenarioResult:
    next_rule_multiplier = _setup_rule_multiplier(len(remaining_setup_keys), cfg)
    combined_rule_multiplier = _combine_rule_multiplier(process_data, rule.rule_multiplier, next_rule_multiplier)
    direct_snapshot = recompute_cost_snapshot(process_data, rule_multiplier=combined_rule_multiplier)
    next_machine_rate = cfg.machine_hourly_rate_3_axis_eur if _is_flip_only(remaining_setup_keys) else cfg.machine_hourly_rate_5_axis_eur
    final_snapshot = recompute_cost_snapshot(
        process_data,
        rule_multiplier=combined_rule_multiplier,
        machine_hourly_rate_eur=next_machine_rate,
    )
    label = "Reduce setup directions"
    return _ScenarioResult(label=label, direct_snapshot=direct_snapshot, final_snapshot=final_snapshot)


def _choose_best_setup_result(
    current_setup_keys: Sequence[str],
    remove_count: int,
    rule: RuleResult,
    process_data: PartProcessData,
    cfg: Config,
    predicate: Optional[Callable[[Sequence[str]], bool]] = None,
) -> Optional[tuple[Sequence[str], _ScenarioResult]]:
    best: Optional[tuple[Sequence[str], _ScenarioResult]] = None
    current = list(current_setup_keys)
    if remove_count <= 0 or remove_count > len(current):
        return None
    for removed_keys in combinations(current, remove_count):
        remaining = [key for key in current if key not in removed_keys]
        if predicate is not None and not predicate(remaining):
            continue
        result = _evaluate_setup_scenario(remaining, rule, process_data, cfg)
        if best is None or result.final_snapshot.unit_cost_eur < best[1].final_snapshot.unit_cost_eur:
            best = (remaining, result)
    return best


def _setup_breakdowns(
    baseline: _CostSnapshot,
    conservative: _ScenarioResult,
    optimistic: _ScenarioResult,
    rule_label: str,
) -> tuple[List[CostImpactBreakdown], List[CostImpactBreakdown]]:
    direct = [
        _make_breakdown(
            rule_label,
            _savings(baseline.unit_cost_eur, conservative.direct_snapshot.unit_cost_eur),
            _savings(baseline.unit_cost_eur, optimistic.direct_snapshot.unit_cost_eur),
            _savings(baseline.batch_cost_eur, conservative.direct_snapshot.batch_cost_eur),
            _savings(baseline.batch_cost_eur, optimistic.direct_snapshot.batch_cost_eur),
            f"{baseline.rule_multiplier:.2f}x -> {conservative.direct_snapshot.rule_multiplier:.2f}x to {optimistic.direct_snapshot.rule_multiplier:.2f}x",
        )
    ]
    conservative_linked_unit = _savings(conservative.direct_snapshot.unit_cost_eur, conservative.final_snapshot.unit_cost_eur)
    optimistic_linked_unit = _savings(optimistic.direct_snapshot.unit_cost_eur, optimistic.final_snapshot.unit_cost_eur)
    conservative_linked_batch = _savings(conservative.direct_snapshot.batch_cost_eur, conservative.final_snapshot.batch_cost_eur)
    optimistic_linked_batch = _savings(optimistic.direct_snapshot.batch_cost_eur, optimistic.final_snapshot.batch_cost_eur)
    linked: List[CostImpactBreakdown] = []
    if max(conservative_linked_unit, optimistic_linked_unit, conservative_linked_batch, optimistic_linked_batch) > 1e-9:
        linked.append(
            _make_breakdown(
                "Machine-rate change",
                conservative_linked_unit,
                optimistic_linked_unit,
                conservative_linked_batch,
                optimistic_linked_batch,
                f"{baseline.machine_hourly_rate_eur:.0f} EUR/hr -> {optimistic.final_snapshot.machine_hourly_rate_eur:.0f} EUR/hr when setup access becomes 3-axis or flip-only",
            )
        )
    return direct, linked


def _rule5_impact(
    recommendation: Recommendation,
    rule: RuleResult,
    process_data: PartProcessData,
    cfg: Config,
    baseline: _CostSnapshot,
) -> Optional[CostImpactRange]:
    current_setup_keys = _parse_setup_keys(rule.feature_insights)
    if not current_setup_keys or len(current_setup_keys) <= cfg.max_setups:
        return None

    def group_impact(insight: FeatureInsight) -> Optional[CostImpactRange]:
        removed_key_match = re.search(r"requiring the\s+([XYZ][+-])\s+setup direction", insight.summary)
        if removed_key_match is None:
            return None
        removed_key = removed_key_match.group(1)
        remaining = [key for key in current_setup_keys if key != removed_key]
        result = _evaluate_setup_scenario(remaining, rule, process_data, cfg)
        direct, linked = _setup_breakdowns(baseline, result, result, "Rule 5 multiplier")
        return _build_cost_impact(
            baseline,
            _ScenarioResult(f"Eliminate the {removed_key} setup direction", result.direct_snapshot, result.final_snapshot),
            _ScenarioResult(f"Eliminate the {removed_key} setup direction", result.direct_snapshot, result.final_snapshot),
            "Each removable setup direction is evaluated against the current setup-count rule and machine-rate logic.",
            direct,
            linked,
        )

    best = _best_feature(recommendation, group_impact)
    if best is None:
        return None
    conservative_choice = _choose_best_setup_result(current_setup_keys, 1, rule, process_data, cfg)
    optimistic_remove_count = len(current_setup_keys) - cfg.max_setups
    optimistic_choice = _choose_best_setup_result(current_setup_keys, optimistic_remove_count, rule, process_data, cfg)
    if conservative_choice is None or optimistic_choice is None:
        return None
    conservative = _ScenarioResult(
        "Eliminate the single most expensive setup direction",
        conservative_choice[1].direct_snapshot,
        conservative_choice[1].final_snapshot,
    )
    optimistic = _ScenarioResult(
        "Reduce setup directions to the modeled threshold",
        optimistic_choice[1].direct_snapshot,
        optimistic_choice[1].final_snapshot,
    )
    direct, linked = _setup_breakdowns(baseline, conservative, optimistic, "Rule 5 multiplier")
    return _build_cost_impact(
        baseline,
        conservative,
        optimistic,
        "Savings come from lowering the Rule 5 setup multiplier, with machine-rate savings broken out when the remaining access pattern becomes 3-axis or flip-only.",
        direct,
        linked,
    )


def _process_machine_impact(
    recommendation: Recommendation,
    rule: RuleResult,
    process_data: PartProcessData,
    cfg: Config,
    baseline: _CostSnapshot,
) -> Optional[CostImpactRange]:
    if process_data.machine_type != "5-axis":
        return None
    current_setup_keys = _parse_setup_keys(rule.feature_insights)
    if not current_setup_keys:
        return None

    def three_axis(remaining: Sequence[str]) -> bool:
        return _is_flip_only(remaining)

    def group_impact(insight: FeatureInsight) -> Optional[CostImpactRange]:
        match = re.search(r"requiring the\s+([XYZ][+-])\s+setup direction", insight.summary)
        if match is None:
            return None
        remaining = [key for key in current_setup_keys if key != match.group(1)]
        if not three_axis(remaining):
            return None
        result = _evaluate_setup_scenario(remaining, rule, process_data, cfg)
        direct, linked = _setup_breakdowns(baseline, result, result, "Rule 5 multiplier")
        return _build_cost_impact(
            baseline,
            _ScenarioResult(f"Remove {match.group(1)} and stay 3-axis/flip-only", result.direct_snapshot, result.final_snapshot),
            _ScenarioResult(f"Remove {match.group(1)} and stay 3-axis/flip-only", result.direct_snapshot, result.final_snapshot),
            "This estimate only counts deterministic savings from moving the current setup access back onto the 3-axis machine-rate band.",
            direct,
            linked,
        )

    _best_feature(recommendation, group_impact)
    conservative_choice: Optional[tuple[Sequence[str], _ScenarioResult]] = None
    for remove_count in range(1, len(current_setup_keys) + 1):
        conservative_choice = _choose_best_setup_result(
            current_setup_keys,
            remove_count,
            rule,
            process_data,
            cfg,
            predicate=three_axis,
        )
        if conservative_choice is not None:
            break
    optimistic_choice = None
    for remove_count in range(1, len(current_setup_keys) + 1):
        candidate = _choose_best_setup_result(
            current_setup_keys,
            remove_count,
            rule,
            process_data,
            cfg,
            predicate=three_axis,
        )
        if candidate is None:
            continue
        if optimistic_choice is None or candidate[1].final_snapshot.unit_cost_eur < optimistic_choice[1].final_snapshot.unit_cost_eur:
            optimistic_choice = candidate
    if conservative_choice is None or optimistic_choice is None:
        return None
    conservative = _ScenarioResult(
        "Make the smallest setup change that gets back to 3-axis/flip-only",
        conservative_choice[1].direct_snapshot,
        conservative_choice[1].final_snapshot,
    )
    optimistic = _ScenarioResult(
        "Choose the lowest-cost 3-axis/flip-only access pattern",
        optimistic_choice[1].direct_snapshot,
        optimistic_choice[1].final_snapshot,
    )
    direct, linked = _setup_breakdowns(baseline, conservative, optimistic, "Rule 5 multiplier")
    return _build_cost_impact(
        baseline,
        conservative,
        optimistic,
        "Savings come from staying inside the existing 3-axis/flip-only machine-rate logic; linked machine-rate savings are separated from any Rule 5 multiplier change.",
        direct,
        linked,
    )


def _count_multiplier_impact(
    recommendation: Recommendation,
    *,
    process_data: PartProcessData,
    baseline: _CostSnapshot,
    count: int,
    current_multiplier: float,
    per_feature_penalty: float,
    max_multiplier: float,
    label: str,
    count_label: str,
    update_attr: str,
) -> Optional[CostImpactRange]:
    if count <= 0:
        return None

    def next_multiplier(removed_count: int) -> float:
        return min(max_multiplier, 1.0 + (per_feature_penalty * max(0, count - removed_count)))

    def snapshot_for(removed_count: int) -> _CostSnapshot:
        next_value = next_multiplier(removed_count)
        kwargs = {"hole_count_multiplier": next_value} if update_attr == "hole" else {"radius_count_multiplier": next_value}
        return recompute_cost_snapshot(process_data, **kwargs)

    def feature_impact(_insight: FeatureInsight) -> Optional[CostImpactRange]:
        snapshot = snapshot_for(1)
        scenario = _ScenarioResult(f"Remove one counted {count_label}", snapshot, snapshot)
        direct_breakdown = [
            _make_breakdown(
                label,
                _savings(baseline.unit_cost_eur, snapshot.unit_cost_eur),
                _savings(baseline.unit_cost_eur, snapshot.unit_cost_eur),
                _savings(baseline.batch_cost_eur, snapshot.batch_cost_eur),
                _savings(baseline.batch_cost_eur, snapshot.batch_cost_eur),
                f"{current_multiplier:.2f}x -> {next_multiplier(1):.2f}x",
            )
        ]
        return _build_cost_impact(
            baseline,
            scenario,
            scenario,
            f"Each removed counted {count_label} reduces the current {label.lower()} by one modeled increment.",
            direct_breakdown,
            [],
        )

    _best_feature(recommendation, feature_impact)
    conservative_snapshot = snapshot_for(1)
    optimistic_snapshot = snapshot_for(count)
    conservative = _ScenarioResult(f"Remove one counted {count_label}", conservative_snapshot, conservative_snapshot)
    optimistic = _ScenarioResult(f"Remove every counted {count_label}", optimistic_snapshot, optimistic_snapshot)
    direct_breakdown = [
        _make_breakdown(
            label,
            _savings(baseline.unit_cost_eur, conservative_snapshot.unit_cost_eur),
            _savings(baseline.unit_cost_eur, optimistic_snapshot.unit_cost_eur),
            _savings(baseline.batch_cost_eur, conservative_snapshot.batch_cost_eur),
            _savings(baseline.batch_cost_eur, optimistic_snapshot.batch_cost_eur),
            f"{current_multiplier:.2f}x -> {next_multiplier(1):.2f}x to {next_multiplier(count):.2f}x",
        )
    ]
    return _build_cost_impact(
        baseline,
        conservative,
        optimistic,
        f"Savings come from lowering the current {label.lower()} inside the existing machining-cost formula.",
        direct_breakdown,
        [],
    )
