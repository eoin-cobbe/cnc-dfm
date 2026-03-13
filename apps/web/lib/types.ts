export interface AnalysisRuntimeStatus {
  available: boolean;
  errorType?: string;
  message?: string;
}

export interface HealthResponse {
  status: string;
  apiVersion: number;
  configPath: string;
  configExists: boolean;
  pythonExecutable: string;
  platform: string;
  cwd: string;
  analysisRuntime: AnalysisRuntimeStatus;
  webApi?: {
    origins: string[];
    previewBaseUrl: string;
    overlayBaseUrl: string;
  };
}

export interface MaterialSpec {
  key: string;
  label: string;
  density_kg_per_m3: number;
  machinability_index: number;
  machinability_source: string;
  baseline_billet_cost_eur_per_kg: number;
  baseline_billet_cost_source: string;
  baseline_fixed_stock_cost_eur: number;
  baseline_fixed_stock_cost_source: string;
}

export interface MaterialsResponse {
  materials: MaterialSpec[];
}

export interface ConfigValues {
  min_radius: number;
  max_pocket_ratio: number;
  max_tool_depth_ratio: number;
  min_wall: number;
  max_hole_ratio: number;
  max_setups: number;
  material: string;
  baseline_6061_mrr: number;
  machine_hourly_rate_3_axis_eur: number;
  machine_hourly_rate_5_axis_eur: number;
  material_billet_cost_eur_per_kg: number;
  surface_penalty_slope: number;
  surface_penalty_max_multiplier: number;
  complexity_penalty_per_face: number;
  complexity_penalty_max_multiplier: number;
  complexity_baseline_faces: number;
  hole_count_penalty_per_feature: number;
  hole_count_penalty_max_multiplier: number;
  radius_count_penalty_per_feature: number;
  radius_count_penalty_max_multiplier: number;
  qty_learning_rate: number;
  qty_factor_floor: number;
}

export interface ConfigResponse {
  configPath: string;
  hasSavedConfig: boolean;
  values: ConfigValues;
}

export interface Point3 {
  x: number;
  y: number;
  z: number;
}

export interface CostImpactBreakdown {
  label: string;
  minimum_unit_savings_eur: number;
  maximum_unit_savings_eur: number;
  minimum_batch_savings_eur: number;
  maximum_batch_savings_eur: number;
  details: string;
}

export interface CostImpactRange {
  current_unit_cost_eur: number;
  current_batch_cost_eur: number;
  minimum_unit_savings_eur: number;
  maximum_unit_savings_eur: number;
  minimum_batch_savings_eur: number;
  maximum_batch_savings_eur: number;
  minimum_percent_savings: number;
  maximum_percent_savings: number;
  conservative_label: string;
  optimistic_label: string;
  rationale: string;
  direct_breakdown: CostImpactBreakdown[];
  linked_breakdown: CostImpactBreakdown[];
}

export interface FeatureInsight {
  id: string;
  summary: string;
  highlight_kind: string;
  axis?: string;
  measured_value?: number;
  target_value?: number;
  units?: string;
  anchor?: Point3;
  segment_start?: Point3;
  segment_end?: Point3;
  overlay_mesh_paths: string[];
  cost_impact?: CostImpactRange;
}

export interface Recommendation {
  kind: string;
  priority: number;
  title: string;
  summary: string;
  impact: string;
  actions: string[];
  source: string;
  feature_insights: FeatureInsight[];
  cost_impact?: CostImpactRange;
}

export interface AnalysisSummary {
  passed: boolean;
  total_rule_count: number;
  passed_rule_count: number;
  failed_rule_count: number;
  rule_multiplier: number;
}

export interface Rule {
  name: string;
  passed: boolean;
  summary: string;
  details: string;
  detected_features: number;
  passed_features: number;
  failed_features: number;
  axis_breakdown?: Record<string, [number, number, number]>;
  minimum_detected?: number;
  required_minimum?: number;
  metric_label?: string;
  average_detected?: number;
  threshold?: number;
  threshold_kind?: string;
  rule_multiplier: number;
}

export interface PartProcessData {
  material_key: string;
  material_label: string;
  part_bbox_x_mm: number;
  part_bbox_y_mm: number;
  part_bbox_z_mm: number;
  stock_bbox_x_mm: number;
  stock_bbox_y_mm: number;
  stock_bbox_z_mm: number;
  volume_mm3: number;
  stock_volume_mm3: number;
  removed_volume_mm3: number;
  part_surface_area_mm2: number;
  part_sav_ratio: number;
  bbox_sav_ratio: number;
  surface_area_ratio: number;
  surface_area_multiplier: number;
  surface_complexity_faces: number;
  complexity_multiplier: number;
  density_kg_per_m3: number;
  mass_kg: number;
  stock_mass_kg: number;
  material_billet_cost_eur_per_kg: number;
  material_fixed_cost_eur: number;
  material_stock_cost_eur: number;
  material_billet_cost_source: string;
  material_fixed_cost_source: string;
  required_setup_directions: string;
  machine_type: string;
  hole_count: number;
  hole_count_multiplier: number;
  radius_count: number;
  radius_count_multiplier: number;
  machinability_index: number;
  machinability_source: string;
  baseline_6061_mrr_mm3_per_min: number;
  material_time_multiplier: number;
  rule_multiplier: number;
  total_time_multiplier: number;
  qty: number;
  qty_multiplier: number;
  estimated_roughing_mrr_mm3_per_min: number;
  roughing_time_min: number;
  base_machining_time_min: number;
  machining_time_min: number;
  machine_hourly_rate_eur: number;
  roughing_cost: number;
  machining_cost: number;
  total_estimated_cost_eur: number;
  batch_total_estimated_cost_eur: number;
}

export interface Analysis {
  file_path: string;
  process_data: PartProcessData;
  rules: Rule[];
  summary: AnalysisSummary;
  recommendations: Recommendation[];
}

export interface AnalyzeResponse {
  analysis: Analysis;
  previewUrl: string | null;
  uploadedFileName: string;
  config: ConfigValues;
}
