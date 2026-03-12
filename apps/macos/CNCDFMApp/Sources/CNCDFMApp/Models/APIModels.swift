import Foundation

struct APIErrorEnvelope: Decodable {
    let error: APIErrorPayload
}

struct APIErrorPayload: Decodable {
    let type: String
    let message: String
}

struct HealthResponse: Decodable {
    let status: String
    let apiVersion: Int
    let configPath: String
    let configExists: Bool
    let pythonExecutable: String
    let platform: String
    let cwd: String
    let analysisRuntime: AnalysisRuntimeStatus

    enum CodingKeys: String, CodingKey {
        case status
        case apiVersion = "apiVersion"
        case configPath = "configPath"
        case configExists = "configExists"
        case pythonExecutable = "pythonExecutable"
        case platform
        case cwd
        case analysisRuntime = "analysisRuntime"
    }
}

struct AnalysisRuntimeStatus: Decodable {
    let available: Bool
    let errorType: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case available
        case errorType = "errorType"
        case message
    }
}

struct ConfigResponse: Decodable {
    let configPath: String
    let hasSavedConfig: Bool
    let values: ConfigValues

    enum CodingKeys: String, CodingKey {
        case configPath = "configPath"
        case hasSavedConfig = "hasSavedConfig"
        case values
    }
}

struct MaterialsResponse: Decodable {
    let materials: [MaterialSpecPayload]
}

struct PreviewResponse: Decodable {
    let sourcePath: String
    let previewPath: String
    let format: String

    enum CodingKeys: String, CodingKey {
        case sourcePath = "sourcePath"
        case previewPath = "previewPath"
        case format
    }
}

struct MaterialSpecPayload: Decodable, Identifiable {
    let key: String
    let label: String
    let densityKgPerM3: Double
    let machinabilityIndex: Double
    let machinabilitySource: String
    let baselineBilletCostEurPerKg: Double
    let baselineBilletCostSource: String
    let baselineFixedStockCostEur: Double
    let baselineFixedStockCostSource: String

    var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key
        case label
        case densityKgPerM3 = "density_kg_per_m3"
        case machinabilityIndex = "machinability_index"
        case machinabilitySource = "machinability_source"
        case baselineBilletCostEurPerKg = "baseline_billet_cost_eur_per_kg"
        case baselineBilletCostSource = "baseline_billet_cost_source"
        case baselineFixedStockCostEur = "baseline_fixed_stock_cost_eur"
        case baselineFixedStockCostSource = "baseline_fixed_stock_cost_source"
    }
}

struct ConfigValues: Codable, Equatable {
    var minRadius: Double
    var maxPocketRatio: Double
    var maxToolDepthRatio: Double
    var minWall: Double
    var maxHoleRatio: Double
    var maxSetups: Int
    var material: String
    var baseline6061Mrr: Double
    var machineHourlyRate3AxisEur: Double
    var machineHourlyRate5AxisEur: Double
    var materialBilletCostEurPerKg: Double
    var surfacePenaltySlope: Double
    var surfacePenaltyMaxMultiplier: Double
    var complexityPenaltyPerFace: Double
    var complexityPenaltyMaxMultiplier: Double
    var complexityBaselineFaces: Int
    var holeCountPenaltyPerFeature: Double
    var holeCountPenaltyMaxMultiplier: Double
    var radiusCountPenaltyPerFeature: Double
    var radiusCountPenaltyMaxMultiplier: Double
    var qtyLearningRate: Double
    var qtyFactorFloor: Double

    enum CodingKeys: String, CodingKey {
        case minRadius = "min_radius"
        case maxPocketRatio = "max_pocket_ratio"
        case maxToolDepthRatio = "max_tool_depth_ratio"
        case minWall = "min_wall"
        case maxHoleRatio = "max_hole_ratio"
        case maxSetups = "max_setups"
        case material
        case baseline6061Mrr = "baseline_6061_mrr"
        case machineHourlyRate3AxisEur = "machine_hourly_rate_3_axis_eur"
        case machineHourlyRate5AxisEur = "machine_hourly_rate_5_axis_eur"
        case materialBilletCostEurPerKg = "material_billet_cost_eur_per_kg"
        case surfacePenaltySlope = "surface_penalty_slope"
        case surfacePenaltyMaxMultiplier = "surface_penalty_max_multiplier"
        case complexityPenaltyPerFace = "complexity_penalty_per_face"
        case complexityPenaltyMaxMultiplier = "complexity_penalty_max_multiplier"
        case complexityBaselineFaces = "complexity_baseline_faces"
        case holeCountPenaltyPerFeature = "hole_count_penalty_per_feature"
        case holeCountPenaltyMaxMultiplier = "hole_count_penalty_max_multiplier"
        case radiusCountPenaltyPerFeature = "radius_count_penalty_per_feature"
        case radiusCountPenaltyMaxMultiplier = "radius_count_penalty_max_multiplier"
        case qtyLearningRate = "qty_learning_rate"
        case qtyFactorFloor = "qty_factor_floor"
    }
}

struct AnalysisResponse: Decodable {
    let filePath: String
    let processData: PartProcessDataPayload
    let rules: [RulePayload]
    let summary: AnalysisSummaryPayload
    let recommendations: [RecommendationPayload]

    enum CodingKeys: String, CodingKey {
        case filePath = "file_path"
        case processData = "process_data"
        case rules
        case summary
        case recommendations
    }
}

struct RecommendationPayload: Decodable, Identifiable {
    let kind: String
    let priority: Int
    let title: String
    let summary: String
    let impact: String
    let actions: [String]
    let source: String

    var id: String { "\(kind)-\(source)-\(title)" }
}

struct AnalysisSummaryPayload: Decodable {
    let passed: Bool
    let totalRuleCount: Int
    let passedRuleCount: Int
    let failedRuleCount: Int
    let ruleMultiplier: Double

    enum CodingKeys: String, CodingKey {
        case passed
        case totalRuleCount = "total_rule_count"
        case passedRuleCount = "passed_rule_count"
        case failedRuleCount = "failed_rule_count"
        case ruleMultiplier = "rule_multiplier"
    }
}

struct RulePayload: Decodable, Identifiable {
    let name: String
    let passed: Bool
    let summary: String
    let details: String
    let detectedFeatures: Int
    let passedFeatures: Int
    let failedFeatures: Int
    let axisBreakdown: [String: [Int]]?
    let minimumDetected: Double?
    let requiredMinimum: Double?
    let metricLabel: String?
    let averageDetected: Double?
    let threshold: Double?
    let thresholdKind: String?
    let ruleMultiplier: Double

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name
        case passed
        case summary
        case details
        case detectedFeatures = "detected_features"
        case passedFeatures = "passed_features"
        case failedFeatures = "failed_features"
        case axisBreakdown = "axis_breakdown"
        case minimumDetected = "minimum_detected"
        case requiredMinimum = "required_minimum"
        case metricLabel = "metric_label"
        case averageDetected = "average_detected"
        case threshold
        case thresholdKind = "threshold_kind"
        case ruleMultiplier = "rule_multiplier"
    }
}

struct PartProcessDataPayload: Decodable {
    let materialKey: String
    let materialLabel: String
    let partBBoxXMm: Double
    let partBBoxYMm: Double
    let partBBoxZMm: Double
    let stockBBoxXMm: Double
    let stockBBoxYMm: Double
    let stockBBoxZMm: Double
    let volumeMm3: Double
    let stockVolumeMm3: Double
    let removedVolumeMm3: Double
    let partSurfaceAreaMm2: Double
    let partSavRatio: Double
    let bboxSavRatio: Double
    let surfaceAreaRatio: Double
    let surfaceAreaMultiplier: Double
    let surfaceComplexityFaces: Int
    let complexityMultiplier: Double
    let densityKgPerM3: Double
    let massKg: Double
    let stockMassKg: Double
    let materialBilletCostEurPerKg: Double
    let materialFixedCostEur: Double
    let materialStockCostEur: Double
    let materialBilletCostSource: String
    let materialFixedCostSource: String
    let requiredSetupDirections: String
    let machineType: String
    let holeCount: Int
    let holeCountMultiplier: Double
    let radiusCount: Int
    let radiusCountMultiplier: Double
    let machinabilityIndex: Double
    let machinabilitySource: String
    let baseline6061MrrMm3PerMin: Double
    let materialTimeMultiplier: Double
    let ruleMultiplier: Double
    let totalTimeMultiplier: Double
    let qty: Int
    let qtyMultiplier: Double
    let estimatedRoughingMrrMm3PerMin: Double
    let roughingTimeMin: Double
    let baseMachiningTimeMin: Double
    let machiningTimeMin: Double
    let machineHourlyRateEur: Double
    let roughingCost: Double
    let machiningCost: Double
    let totalEstimatedCostEur: Double
    let batchTotalEstimatedCostEur: Double

    enum CodingKeys: String, CodingKey {
        case materialKey = "material_key"
        case materialLabel = "material_label"
        case partBBoxXMm = "part_bbox_x_mm"
        case partBBoxYMm = "part_bbox_y_mm"
        case partBBoxZMm = "part_bbox_z_mm"
        case stockBBoxXMm = "stock_bbox_x_mm"
        case stockBBoxYMm = "stock_bbox_y_mm"
        case stockBBoxZMm = "stock_bbox_z_mm"
        case volumeMm3 = "volume_mm3"
        case stockVolumeMm3 = "stock_volume_mm3"
        case removedVolumeMm3 = "removed_volume_mm3"
        case partSurfaceAreaMm2 = "part_surface_area_mm2"
        case partSavRatio = "part_sav_ratio"
        case bboxSavRatio = "bbox_sav_ratio"
        case surfaceAreaRatio = "surface_area_ratio"
        case surfaceAreaMultiplier = "surface_area_multiplier"
        case surfaceComplexityFaces = "surface_complexity_faces"
        case complexityMultiplier = "complexity_multiplier"
        case densityKgPerM3 = "density_kg_per_m3"
        case massKg = "mass_kg"
        case stockMassKg = "stock_mass_kg"
        case materialBilletCostEurPerKg = "material_billet_cost_eur_per_kg"
        case materialFixedCostEur = "material_fixed_cost_eur"
        case materialStockCostEur = "material_stock_cost_eur"
        case materialBilletCostSource = "material_billet_cost_source"
        case materialFixedCostSource = "material_fixed_cost_source"
        case requiredSetupDirections = "required_setup_directions"
        case machineType = "machine_type"
        case holeCount = "hole_count"
        case holeCountMultiplier = "hole_count_multiplier"
        case radiusCount = "radius_count"
        case radiusCountMultiplier = "radius_count_multiplier"
        case machinabilityIndex = "machinability_index"
        case machinabilitySource = "machinability_source"
        case baseline6061MrrMm3PerMin = "baseline_6061_mrr_mm3_per_min"
        case materialTimeMultiplier = "material_time_multiplier"
        case ruleMultiplier = "rule_multiplier"
        case totalTimeMultiplier = "total_time_multiplier"
        case qty
        case qtyMultiplier = "qty_multiplier"
        case estimatedRoughingMrrMm3PerMin = "estimated_roughing_mrr_mm3_per_min"
        case roughingTimeMin = "roughing_time_min"
        case baseMachiningTimeMin = "base_machining_time_min"
        case machiningTimeMin = "machining_time_min"
        case machineHourlyRateEur = "machine_hourly_rate_eur"
        case roughingCost = "roughing_cost"
        case machiningCost = "machining_cost"
        case totalEstimatedCostEur = "total_estimated_cost_eur"
        case batchTotalEstimatedCostEur = "batch_total_estimated_cost_eur"
    }
}
