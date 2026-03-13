import Foundation
import Testing
@testable import CNCDFMApp

struct APIModelsTests {
    @Test
    func recommendationDecodesCostImpactPayload() throws {
        let json = """
        {
          "file_path": "/tmp/part.step",
          "process_data": {
            "material_key": "test",
            "material_label": "Test",
            "part_bbox_x_mm": 40.0,
            "part_bbox_y_mm": 30.0,
            "part_bbox_z_mm": 20.0,
            "stock_bbox_x_mm": 50.0,
            "stock_bbox_y_mm": 40.0,
            "stock_bbox_z_mm": 30.0,
            "volume_mm3": 12000.0,
            "stock_volume_mm3": 60000.0,
            "removed_volume_mm3": 48000.0,
            "part_surface_area_mm2": 6000.0,
            "part_sav_ratio": 0.5,
            "bbox_sav_ratio": 0.3,
            "surface_area_ratio": 1.2,
            "surface_area_multiplier": 1.1,
            "surface_complexity_faces": 12,
            "complexity_multiplier": 1.05,
            "density_kg_per_m3": 2700.0,
            "mass_kg": 0.03,
            "stock_mass_kg": 0.09,
            "material_billet_cost_eur_per_kg": 10.0,
            "material_fixed_cost_eur": 3.0,
            "material_stock_cost_eur": 9.0,
            "material_billet_cost_source": "test",
            "material_fixed_cost_source": "test",
            "required_setup_directions": "X+, X-",
            "machine_type": "3-axis",
            "hole_count": 4,
            "hole_count_multiplier": 1.08,
            "radius_count": 2,
            "radius_count_multiplier": 1.02,
            "machinability_index": 1.0,
            "machinability_source": "test",
            "baseline_6061_mrr_mm3_per_min": 20000.0,
            "material_time_multiplier": 1.0,
            "rule_multiplier": 1.4,
            "total_time_multiplier": 1.7,
            "qty": 2,
            "qty_multiplier": 0.8,
            "estimated_roughing_mrr_mm3_per_min": 20000.0,
            "roughing_time_min": 30.0,
            "base_machining_time_min": 50.0,
            "machining_time_min": 50.0,
            "machine_hourly_rate_eur": 50.0,
            "roughing_cost": 25.0,
            "machining_cost": 33.0,
            "total_estimated_cost_eur": 42.0,
            "batch_total_estimated_cost_eur": 84.0
          },
          "rules": [],
          "summary": {
            "passed": false,
            "total_rule_count": 6,
            "passed_rule_count": 5,
            "failed_rule_count": 1,
            "rule_multiplier": 1.4
          },
          "recommendations": [
            {
              "kind": "cost",
              "priority": 80,
              "title": "Shorten or enlarge deep holes",
              "summary": "Test recommendation",
              "impact": "Test impact",
              "actions": ["Action 1"],
              "source": "Rule 4 — Hole Depth vs Diameter",
              "cost_impact": {
                "current_unit_cost_eur": 42.0,
                "current_batch_cost_eur": 84.0,
                "minimum_unit_savings_eur": 3.0,
                "maximum_unit_savings_eur": 8.0,
                "minimum_batch_savings_eur": 6.0,
                "maximum_batch_savings_eur": 16.0,
                "minimum_percent_savings": 7.1,
                "maximum_percent_savings": 19.0,
                "conservative_label": "Fix the single worst flagged feature",
                "optimistic_label": "Fix every flagged feature to the modeled threshold",
                "rationale": "Savings come from reducing the affected rule multiplier.",
                "direct_breakdown": [
                  {
                    "label": "Rule 4 multiplier",
                    "minimum_unit_savings_eur": 3.0,
                    "maximum_unit_savings_eur": 8.0,
                    "minimum_batch_savings_eur": 6.0,
                    "maximum_batch_savings_eur": 16.0,
                    "details": "1.40x -> 1.20x to 1.00x"
                  }
                ],
                "linked_breakdown": []
              },
              "feature_insights": [
                {
                  "id": "hole-a",
                  "summary": "Hole group",
                  "highlight_kind": "hole",
                  "measured_value": 6.0,
                  "target_value": 4.0,
                  "units": "ratio",
                  "overlay_mesh_paths": [],
                  "cost_impact": {
                    "current_unit_cost_eur": 42.0,
                    "current_batch_cost_eur": 84.0,
                    "minimum_unit_savings_eur": 3.0,
                    "maximum_unit_savings_eur": 3.0,
                    "minimum_batch_savings_eur": 6.0,
                    "maximum_batch_savings_eur": 6.0,
                    "minimum_percent_savings": 7.1,
                    "maximum_percent_savings": 7.1,
                    "conservative_label": "Fix this feature",
                    "optimistic_label": "Fix this feature",
                    "rationale": "Feature level savings.",
                    "direct_breakdown": [],
                    "linked_breakdown": []
                  }
                },
                {
                  "id": "hole-b",
                  "summary": "Hole group",
                  "highlight_kind": "hole",
                  "measured_value": 5.0,
                  "target_value": 4.0,
                  "units": "ratio",
                  "overlay_mesh_paths": []
                }
              ]
            }
          ]
        }
        """

        let response = try JSONDecoder().decode(AnalysisResponse.self, from: Data(json.utf8))
        let recommendation = try #require(response.recommendations.first)
        let costImpact = try #require(recommendation.costImpact)
        let featureCostImpact = try #require(recommendation.featureInsights.first?.costImpact)

        #expect(costImpact.minimumUnitSavingsEur == 3.0)
        #expect(costImpact.maximumUnitSavingsEur == 8.0)
        #expect(costImpact.directBreakdown.first?.label == "Rule 4 multiplier")
        #expect(featureCostImpact.maximumBatchSavingsEur == 6.0)
    }

    @Test
    func recommendationFeatureGroupsStillGroupInsightsWithCostImpact() throws {
        let json = """
        {
          "kind": "cost",
          "priority": 80,
          "title": "Grouped",
          "summary": "Summary",
          "impact": "Impact",
          "actions": [],
          "source": "Rule 4 — Hole Depth vs Diameter",
          "feature_insights": [
            {
              "id": "a",
              "summary": "Shared group",
              "highlight_kind": "hole",
              "measured_value": 6.0,
              "target_value": 4.0,
              "units": "ratio",
              "overlay_mesh_paths": [],
              "cost_impact": {
                "current_unit_cost_eur": 42.0,
                "current_batch_cost_eur": 84.0,
                "minimum_unit_savings_eur": 3.0,
                "maximum_unit_savings_eur": 3.0,
                "minimum_batch_savings_eur": 6.0,
                "maximum_batch_savings_eur": 6.0,
                "minimum_percent_savings": 7.1,
                "maximum_percent_savings": 7.1,
                "conservative_label": "Fix",
                "optimistic_label": "Fix",
                "rationale": "Feature",
                "direct_breakdown": [],
                "linked_breakdown": []
              }
            },
            {
              "id": "b",
              "summary": "Shared group",
              "highlight_kind": "hole",
              "measured_value": 5.5,
              "target_value": 4.0,
              "units": "ratio",
              "overlay_mesh_paths": []
            }
          ]
        }
        """

        let recommendation = try JSONDecoder().decode(RecommendationPayload.self, from: Data(json.utf8))
        #expect(recommendation.featureGroups.count == 1)
        #expect(recommendation.featureGroups.first?.instances.count == 2)
        #expect(recommendation.featureGroups.first?.instances.first?.costImpact?.maximumUnitSavingsEur == 3.0)
    }
}
