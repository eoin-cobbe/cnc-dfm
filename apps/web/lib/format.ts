import type { PartProcessData, Recommendation, Rule } from "@/lib/types";

export function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatInteger(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatMultiplier(value: number) {
  return `${formatNumber(value, 2)}x`;
}

export function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}

export function groupFeatureInsights(recommendation: Recommendation | null) {
  if (!recommendation) {
    return [];
  }

  const groups = new Map<string, Recommendation["feature_insights"]>();
  for (const insight of recommendation.feature_insights) {
    const next = groups.get(insight.summary) ?? [];
    next.push(insight);
    groups.set(insight.summary, next);
  }

  return Array.from(groups.entries()).map(([summary, instances]) => ({
    id: summary,
    summary,
    instances,
  }));
}

export function applyQuantityToProcessData(
  data: PartProcessData,
  quantity: number,
  qtyLearningRate: number,
  qtyFactorFloor: number,
): PartProcessData {
  const qtySafe = Math.max(1, quantity);
  const learningRate = Math.max(1e-6, Math.min(qtyLearningRate, 1));
  const factorFloor = Math.max(1e-6, Math.min(qtyFactorFloor, 1));
  const learningExponent = Math.log(learningRate) / Math.log(2);
  const qtyMultiplier = Math.max(factorFloor, Math.pow(qtySafe, learningExponent));
  const qtyAdjustedMachiningTimeMin = data.base_machining_time_min * qtyMultiplier;
  const machiningCost = (qtyAdjustedMachiningTimeMin / 60) * data.machine_hourly_rate_eur;
  const baseMachiningCost = (data.base_machining_time_min / 60) * data.machine_hourly_rate_eur;
  const totalEstimatedCostEur = (data.material_stock_cost_eur + baseMachiningCost) * qtyMultiplier;
  const batchTotalEstimatedCostEur = totalEstimatedCostEur * qtySafe;

  return {
    ...data,
    qty: qtySafe,
    qty_multiplier: qtyMultiplier,
    machining_time_min: qtyAdjustedMachiningTimeMin,
    machining_cost: machiningCost,
    total_estimated_cost_eur: totalEstimatedCostEur,
    batch_total_estimated_cost_eur: batchTotalEstimatedCostEur,
  };
}

export function metricBarData(rule: Rule) {
  if (
    !rule.metric_label ||
    rule.average_detected == null ||
    rule.threshold == null ||
    !rule.threshold_kind ||
    !["min", "max"].includes(rule.threshold_kind)
  ) {
    return null;
  }

  const upper = Math.max(rule.threshold * 2, rule.average_detected * 1.2, 1);
  return {
    legend: rule.threshold_kind === "max" ? "Average vs threshold ceiling" : "Average vs threshold floor",
    metricLine: `${rule.metric_label}: avg ${formatNumber(rule.average_detected)} | threshold ${formatNumber(rule.threshold)}`,
    thresholdPosition: clamp01(rule.threshold / upper),
    averagePosition: clamp01(rule.average_detected / upper),
  };
}
