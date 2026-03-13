from __future__ import annotations

import math
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dfm_cost_impact import _rule1_multiplier, estimate_recommendation_cost_impact, recompute_cost_snapshot
from dfm_models import Config, FeatureInsight, PartProcessData, Recommendation, RuleResult
from dfm_scoring import rule_multiplier_from_threshold


def make_process_data(**overrides) -> PartProcessData:
    values = {
        "material_key": "test_material",
        "material_label": "Test Material",
        "part_bbox_x_mm": 40.0,
        "part_bbox_y_mm": 30.0,
        "part_bbox_z_mm": 20.0,
        "stock_bbox_x_mm": 50.0,
        "stock_bbox_y_mm": 40.0,
        "stock_bbox_z_mm": 30.0,
        "volume_mm3": 12_000.0,
        "stock_volume_mm3": 60_000.0,
        "removed_volume_mm3": 48_000.0,
        "part_surface_area_mm2": 6_000.0,
        "part_sav_ratio": 0.5,
        "bbox_sav_ratio": 0.3,
        "surface_area_ratio": 1.2,
        "surface_area_multiplier": 1.1,
        "surface_complexity_faces": 12,
        "complexity_multiplier": 1.05,
        "density_kg_per_m3": 2_700.0,
        "mass_kg": 0.032,
        "stock_mass_kg": 0.090,
        "material_billet_cost_eur_per_kg": 10.0,
        "material_fixed_cost_eur": 3.0,
        "material_stock_cost_eur": 9.0,
        "material_billet_cost_source": "test",
        "material_fixed_cost_source": "test",
        "required_setup_directions": "X+, X-, Y+",
        "machine_type": "3-axis",
        "hole_count": 0,
        "hole_count_multiplier": 1.0,
        "radius_count": 0,
        "radius_count_multiplier": 1.0,
        "machinability_index": 1.0,
        "machinability_source": "test",
        "baseline_6061_mrr_mm3_per_min": 20_000.0,
        "material_time_multiplier": 1.0,
        "rule_multiplier": 1.0,
        "total_time_multiplier": 1.155,
        "qty": 1,
        "qty_multiplier": 1.0,
        "estimated_roughing_mrr_mm3_per_min": 20_000.0,
        "roughing_time_min": 30.0,
        "base_machining_time_min": 0.0,
        "machining_time_min": 0.0,
        "machine_hourly_rate_eur": 50.0,
        "roughing_cost": 25.0,
        "machining_cost": 0.0,
        "total_estimated_cost_eur": 0.0,
        "batch_total_estimated_cost_eur": 0.0,
    }
    values.update(overrides)
    process_data = PartProcessData(**values)
    snapshot = recompute_cost_snapshot(process_data)
    process_data.base_machining_time_min = snapshot.base_machining_time_min
    process_data.machining_time_min = snapshot.base_machining_time_min
    process_data.machining_cost = (
        snapshot.base_machining_time_min / 60.0 * process_data.machine_hourly_rate_eur * process_data.qty_multiplier
    )
    process_data.total_estimated_cost_eur = snapshot.unit_cost_eur
    process_data.batch_total_estimated_cost_eur = snapshot.batch_cost_eur
    return process_data


class CostImpactTests(unittest.TestCase):
    def test_rule1_recommendation_and_feature_use_range(self) -> None:
        cfg = Config(min_internal_corner_radius_mm=2.0)
        baseline_rule_multiplier = _rule1_multiplier([0.5, 1.4, 3.0], 2.0)
        process_data = make_process_data(rule_multiplier=baseline_rule_multiplier)
        feature_a = FeatureInsight(id="rule1-a", summary="0.50 mm inside corner", measured_value=0.5, target_value=2.0, units="mm")
        feature_b = FeatureInsight(id="rule1-b", summary="1.40 mm inside corner", measured_value=1.4, target_value=2.0, units="mm")
        passing = FeatureInsight(id="rule1-c", summary="3.00 mm inside corner", measured_value=3.0, target_value=2.0, units="mm")
        rule = RuleResult(
            name="Rule 1 — Internal Corner Radius Too Small",
            passed=False,
            summary="FAIL",
            details="test",
            detected_features=3,
            passed_features=1,
            failed_features=2,
            threshold=0.8,
            threshold_kind="min",
            rule_multiplier=baseline_rule_multiplier,
            feature_insights=[feature_a, feature_b],
            all_feature_insights=[feature_a, feature_b, passing],
        )
        recommendation = Recommendation(
            kind="blocker",
            priority=100,
            title="Increase internal corner radii",
            summary="test",
            impact="test",
            actions=[],
            source=rule.name,
            feature_insights=[feature_a, feature_b],
        )

        impact = estimate_recommendation_cost_impact(
            recommendation,
            rules_by_key={"rule1": rule},
            process_data=process_data,
            cfg=cfg,
        )

        self.assertIsNotNone(impact)
        assert impact is not None
        self.assertLess(impact.minimum_unit_savings_eur, impact.maximum_unit_savings_eur)
        self.assertIsNotNone(recommendation.feature_insights[0].cost_impact)
        self.assertGreater(recommendation.feature_insights[0].cost_impact.maximum_unit_savings_eur, 0.0)
        self.assertEqual(recommendation.feature_insights[1].cost_impact.minimum_unit_savings_eur, 0.0)

    def test_threshold_rules_attach_exact_feature_impacts(self) -> None:
        cfg = Config()
        for key, name, threshold, threshold_kind, measured in (
            ("rule2", "Rule 2 — Deep Pocket Ratio", 4.0, "max", 7.0),
            ("rule3", "Rule 3 — Thin Walls", 0.8, "min", 0.4),
            ("rule4", "Rule 4 — Hole Depth vs Diameter", 4.0, "max", 6.0),
            ("rule6", "Rule 6 — Tool Depth to Diameter", 2.0, "max", 3.5),
        ):
            with self.subTest(rule=key):
                process_data = make_process_data(rule_multiplier=1.8)
                insight = FeatureInsight(id=f"{key}-a", summary=f"{key} feature", measured_value=measured, target_value=threshold, units="ratio")
                rule = RuleResult(
                    name=name,
                    passed=False,
                    summary="FAIL",
                    details="test",
                    detected_features=2,
                    passed_features=1,
                    failed_features=1,
                    threshold=threshold,
                    threshold_kind=threshold_kind,
                    rule_multiplier=1.8,
                    feature_insights=[insight],
                    all_feature_insights=[insight, FeatureInsight(id=f"{key}-b", summary="pass", measured_value=threshold, target_value=threshold, units="ratio")],
                )
                recommendation = Recommendation(
                    kind="cost",
                    priority=80,
                    title=name,
                    summary="test",
                    impact="test",
                    actions=[],
                    source=name,
                    feature_insights=[insight],
                )

                impact = estimate_recommendation_cost_impact(
                    recommendation,
                    rules_by_key={key: rule},
                    process_data=process_data,
                    cfg=cfg,
                )

                self.assertIsNotNone(impact)
                assert impact is not None
                self.assertAlmostEqual(impact.minimum_unit_savings_eur, impact.maximum_unit_savings_eur, places=6)
                self.assertIsNotNone(recommendation.feature_insights[0].cost_impact)
                self.assertAlmostEqual(
                    recommendation.feature_insights[0].cost_impact.minimum_unit_savings_eur,
                    recommendation.feature_insights[0].cost_impact.maximum_unit_savings_eur,
                    places=6,
                )

    def test_rule5_includes_linked_machine_rate_savings(self) -> None:
        cfg = Config(max_setups=2, machine_hourly_rate_3_axis_eur=50.0, machine_hourly_rate_5_axis_eur=100.0)
        baseline_rule_multiplier = rule_multiplier_from_threshold(average_detected=4.0, threshold=2.0, threshold_kind="max")
        process_data = make_process_data(
            machine_type="5-axis",
            machine_hourly_rate_eur=100.0,
            rule_multiplier=baseline_rule_multiplier,
            required_setup_directions="X+, X-, Y+, Z+",
        )
        features = [
            FeatureInsight(id="rule5-xplus", summary="4 feature(s) requiring the X+ setup direction."),
            FeatureInsight(id="rule5-xminus", summary="3 feature(s) requiring the X- setup direction."),
            FeatureInsight(id="rule5-yplus", summary="2 feature(s) requiring the Y+ setup direction."),
            FeatureInsight(id="rule5-zplus", summary="1 feature(s) requiring the Z+ setup direction."),
        ]
        rule = RuleResult(
            name="Rule 5 — Multiple Setup Faces",
            passed=False,
            summary="FAIL",
            details="test",
            detected_features=4,
            passed_features=2,
            failed_features=2,
            threshold=2.0,
            threshold_kind="max",
            rule_multiplier=baseline_rule_multiplier,
            feature_insights=features,
        )
        recommendation = Recommendation(
            kind="cost",
            priority=90,
            title="Reduce the number of setup directions",
            summary="test",
            impact="test",
            actions=[],
            source=rule.name,
            feature_insights=features,
        )

        impact = estimate_recommendation_cost_impact(
            recommendation,
            rules_by_key={"rule5": rule},
            process_data=process_data,
            cfg=cfg,
        )

        self.assertIsNotNone(impact)
        assert impact is not None
        self.assertTrue(impact.linked_breakdown)
        self.assertGreater(impact.maximum_unit_savings_eur, impact.minimum_unit_savings_eur)
        self.assertTrue(any(feature.cost_impact is not None for feature in features))

    def test_count_recommendations_have_exact_per_feature_savings(self) -> None:
        cfg = Config(
            hole_count_penalty_per_feature=0.02,
            hole_count_penalty_max_multiplier=1.5,
            radius_count_penalty_per_feature=0.01,
            radius_count_penalty_max_multiplier=1.5,
        )
        for source, key, count, multiplier in (
            ("Hole count", "hole_count", 4, 1.08),
            ("Radius count", "radius_count", 6, 1.06),
        ):
            with self.subTest(source=source):
                process_data = make_process_data(
                    hole_count=count if key == "hole_count" else 0,
                    hole_count_multiplier=multiplier if key == "hole_count" else 1.0,
                    radius_count=count if key == "radius_count" else 0,
                    radius_count_multiplier=multiplier if key == "radius_count" else 1.0,
                )
                insight = FeatureInsight(id=f"{key}-1", summary="feature", measured_value=1.0)
                recommendation = Recommendation(
                    kind="cost",
                    priority=50,
                    title="Count recommendation",
                    summary="test",
                    impact="test",
                    actions=[],
                    source=source,
                    feature_insights=[insight],
                )

                impact = estimate_recommendation_cost_impact(
                    recommendation,
                    rules_by_key={},
                    process_data=process_data,
                    cfg=cfg,
                )

                self.assertIsNotNone(impact)
                assert impact is not None
                self.assertAlmostEqual(impact.minimum_unit_savings_eur, insight.cost_impact.maximum_unit_savings_eur, places=6)
                self.assertAlmostEqual(insight.cost_impact.minimum_unit_savings_eur, insight.cost_impact.maximum_unit_savings_eur, places=6)

    def test_quantity_sensitive_batch_savings_scale_with_qty(self) -> None:
        cfg = Config(hole_count_penalty_per_feature=0.02, hole_count_penalty_max_multiplier=1.5)
        process_data = make_process_data(qty=5, qty_multiplier=0.6, hole_count=5, hole_count_multiplier=1.10)
        recommendation = Recommendation(
            kind="cost",
            priority=50,
            title="Reduce holes",
            summary="test",
            impact="test",
            actions=[],
            source="Hole count",
            feature_insights=[FeatureInsight(id="hole-1", summary="hole", measured_value=1.0)],
        )

        impact = estimate_recommendation_cost_impact(
            recommendation,
            rules_by_key={},
            process_data=process_data,
            cfg=cfg,
        )

        self.assertIsNotNone(impact)
        assert impact is not None
        self.assertTrue(math.isclose(impact.maximum_batch_savings_eur, impact.maximum_unit_savings_eur * process_data.qty, rel_tol=1e-9))

    def test_unsupported_recommendation_returns_none(self) -> None:
        impact = estimate_recommendation_cost_impact(
            Recommendation(
                kind="info",
                priority=0,
                title="Unsupported",
                summary="test",
                impact="test",
                actions=[],
                source="Surface area",
            ),
            rules_by_key={},
            process_data=make_process_data(),
            cfg=Config(),
        )
        self.assertIsNone(impact)


if __name__ == "__main__":
    unittest.main()
