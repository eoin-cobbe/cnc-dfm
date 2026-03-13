"use client";

import { useDeferredValue, useEffect, useRef, useState, useTransition, type ChangeEvent } from "react";
import dynamic from "next/dynamic";

import { analyzeFile, fetchConfig, fetchHealth, fetchMaterials, resolveArtifactUrl, saveConfig } from "@/lib/api";
import { applyQuantityToProcessData, formatCurrency, formatInteger, formatMultiplier, formatNumber, groupFeatureInsights, metricBarData } from "@/lib/format";
import type { Analysis, ConfigValues, CostImpactBreakdown, CostImpactRange, HealthResponse, MaterialSpec, Recommendation } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

const DynamicPartPreview = dynamic(
  () => import("@/components/part-preview").then((module) => module.PartPreview),
  {
    ssr: false,
  },
);

type SidebarScreen = "recommendations" | "ruleResults" | "summary" | "settings" | "diagnostics";

interface ConfigField {
  key: keyof ConfigValues;
  label: string;
  description: string;
  type: "number" | "integer";
  step: string;
}

function SidebarIcon({ name, active }: { name: SidebarScreen; active: boolean }) {
  const stroke = active ? "var(--accent)" : "var(--panel-muted)";
  const commonProps = {
    fill: "none",
    stroke,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.8,
  };

  switch (name) {
    case "recommendations":
      return (
        <svg aria-hidden="true" className="h-[18px] w-[18px]" viewBox="0 0 20 20">
          <path {...commonProps} d="M4 5h10" />
          <path {...commonProps} d="M4 10h7" />
          <path {...commonProps} d="M4 15h8" />
          <path {...commonProps} d="M13 10h3v3" />
          <path {...commonProps} d="M16 13l-4-4" />
        </svg>
      );
    case "ruleResults":
      return (
        <svg aria-hidden="true" className="h-[18px] w-[18px]" viewBox="0 0 20 20">
          <rect {...commonProps} x="4" y="3.5" width="12" height="14" rx="2.2" />
          <path {...commonProps} d="M7 2.8h6" />
          <path {...commonProps} d="M7 8h6" />
          <path {...commonProps} d="M7 11h6" />
          <path {...commonProps} d="M7 14h4" />
        </svg>
      );
    case "summary":
      return (
        <svg aria-hidden="true" className="h-[18px] w-[18px]" viewBox="0 0 20 20">
          <rect {...commonProps} x="4" y="3.5" width="12" height="14" rx="2.2" />
          <path {...commonProps} d="M7 7.5v6" />
          <path {...commonProps} d="M10 10v3.5" />
          <path {...commonProps} d="M13 8.8v4.7" />
          <path {...commonProps} d="M6.5 14.5h7" />
        </svg>
      );
    case "settings":
      return (
        <svg aria-hidden="true" className="h-[18px] w-[18px]" viewBox="0 0 20 20">
          <path {...commonProps} d="M4 5h12" />
          <path {...commonProps} d="M4 10h12" />
          <path {...commonProps} d="M4 15h12" />
          <circle {...commonProps} cx="8" cy="5" r="1.7" />
          <circle {...commonProps} cx="12.5" cy="10" r="1.7" />
          <circle {...commonProps} cx="6.5" cy="15" r="1.7" />
        </svg>
      );
    case "diagnostics":
      return (
        <svg aria-hidden="true" className="h-[18px] w-[18px]" viewBox="0 0 20 20">
          <path {...commonProps} d="M8 4.5c0 1.8-1.2 3-3 3S2 6.3 2 4.5" />
          <path {...commonProps} d="M12 4.5c0 1.8 1.2 3 3 3s3-1.2 3-3" />
          <path {...commonProps} d="M5 7.5v1.8c0 3.1 2.1 5.7 5 6.4 2.9-.7 5-3.3 5-6.4V7.5" />
          <path {...commonProps} d="M10 13.9V17" />
          <circle {...commonProps} cx="10" cy="17" r="1.3" />
        </svg>
      );
    default:
      return null;
  }
}

function NewAnalysisIcon() {
  return (
    <svg aria-hidden="true" className="h-12 w-12" viewBox="0 0 24 24">
      <path
        d="M8 3.5h6.8l4.7 4.7V18a2.5 2.5 0 0 1-2.5 2.5H8A2.5 2.5 0 0 1 5.5 18V6A2.5 2.5 0 0 1 8 3.5Z"
        fill="none"
        stroke="var(--accent)"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.9"
      />
      <path
        d="M14.5 3.8v4.1h4.1"
        fill="none"
        stroke="var(--accent)"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.9"
      />
      <circle cx="7.2" cy="15.9" r="3.6" fill="var(--accent)" />
      <path
        d="M7.2 14.2v3.4M5.5 15.9h3.4"
        fill="none"
        stroke="#ffffff"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.6"
      />
    </svg>
  );
}

const outputScreens: Array<{ id: SidebarScreen; title: string }> = [
  { id: "recommendations", title: "Recommendations" },
  { id: "ruleResults", title: "Rule Results" },
  { id: "summary", title: "Analysis Summary" },
];

const utilityScreens: Array<{ id: SidebarScreen; title: string }> = [
  { id: "settings", title: "Settings" },
  { id: "diagnostics", title: "Diagnostics" },
];

const configSections: Array<{ title: string; fields: ConfigField[] }> = [
  {
    title: "Rules",
    fields: [
      { key: "min_radius", label: "Min Radius", description: "Rule 1 design target in mm.", type: "number", step: "0.1" },
      { key: "max_pocket_ratio", label: "Max Pocket Ratio", description: "Rule 2 pocket depth/opening limit.", type: "number", step: "0.1" },
      { key: "min_wall", label: "Min Wall", description: "Rule 3 minimum wall thickness in mm.", type: "number", step: "0.01" },
      { key: "max_hole_ratio", label: "Max Hole Ratio", description: "Rule 4 hole depth/diameter limit.", type: "number", step: "0.1" },
      { key: "max_setups", label: "Max Setups", description: "Rule 5 setup direction target.", type: "integer", step: "1" },
      { key: "max_tool_depth_ratio", label: "Max Tool Depth Ratio", description: "Rule 6 pocket depth/tool diameter limit.", type: "number", step: "0.1" },
    ],
  },
  {
    title: "Machine And Material",
    fields: [
      { key: "baseline_6061_mrr", label: "Baseline 6061 MRR", description: "Roughing baseline in mm^3/min.", type: "number", step: "1" },
      { key: "machine_hourly_rate_3_axis_eur", label: "3-Axis Rate", description: "Three-axis machine rate in EUR/hr.", type: "number", step: "0.5" },
      { key: "machine_hourly_rate_5_axis_eur", label: "5-Axis Rate", description: "Five-axis machine rate in EUR/hr.", type: "number", step: "0.5" },
      { key: "material_billet_cost_eur_per_kg", label: "Billet Cost", description: "Material cost in EUR/kg.", type: "number", step: "0.01" },
    ],
  },
  {
    title: "Multipliers",
    fields: [
      { key: "surface_penalty_slope", label: "Surface Penalty Slope", description: "Surface-area complexity slope.", type: "number", step: "0.001" },
      { key: "surface_penalty_max_multiplier", label: "Surface Penalty Max", description: "Ceiling for surface penalty multiplier.", type: "number", step: "0.01" },
      { key: "complexity_penalty_per_face", label: "Complexity Penalty", description: "Penalty applied per face above baseline.", type: "number", step: "0.0001" },
      { key: "complexity_penalty_max_multiplier", label: "Complexity Penalty Max", description: "Ceiling for complexity multiplier.", type: "number", step: "0.01" },
      { key: "complexity_baseline_faces", label: "Complexity Baseline Faces", description: "Faces before complexity penalty begins.", type: "integer", step: "1" },
      { key: "hole_count_penalty_per_feature", label: "Hole Penalty", description: "Penalty per detected hole feature.", type: "number", step: "0.001" },
      { key: "hole_count_penalty_max_multiplier", label: "Hole Penalty Max", description: "Ceiling for hole-count multiplier.", type: "number", step: "0.01" },
      { key: "radius_count_penalty_per_feature", label: "Radius Penalty", description: "Penalty per internal radius feature.", type: "number", step: "0.001" },
      { key: "radius_count_penalty_max_multiplier", label: "Radius Penalty Max", description: "Ceiling for radius-count multiplier.", type: "number", step: "0.01" },
      { key: "qty_learning_rate", label: "Qty Learning Rate", description: "Learning-curve reduction per quantity doubling.", type: "number", step: "0.01" },
      { key: "qty_factor_floor", label: "Qty Factor Floor", description: "Minimum quantity multiplier floor.", type: "number", step: "0.01" },
    ],
  },
];

function recommendationTone(kind: Recommendation["kind"]) {
  switch (kind) {
    case "blocker":
      return "danger" as const;
    case "cost":
      return "warning" as const;
    default:
      return "success" as const;
  }
}

function recommendationLabel(kind: Recommendation["kind"]) {
  switch (kind) {
    case "blocker":
      return "Blocker";
    case "cost":
      return "Cost";
    default:
      return "Info";
  }
}

function focusInsight(recommendation: Recommendation | null, selectedFeatureInstanceId: string | null) {
  if (!recommendation) {
    return null;
  }
  return recommendation.feature_insights.find((insight) => insight.id === selectedFeatureInstanceId) ?? recommendation.feature_insights[0] ?? null;
}

function keyValueRows(items: Array<{ label: string; value: string }>) {
  return items.map((item) => (
    <div key={item.label} className="space-y-1">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--panel-muted)]">{item.label}</div>
      <div className="text-sm text-slate-700">{item.value}</div>
    </div>
  ));
}

function smallStat(label: string, value: string) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--panel-muted)]">{label}</div>
      <div className="text-sm font-semibold text-slate-800">{value}</div>
    </div>
  );
}

function formatCurrencyRange(minimum: number, maximum: number) {
  if (Math.abs(minimum - maximum) <= 0.005) {
    return formatCurrency(maximum);
  }
  return `${formatCurrency(minimum)}-${formatCurrency(maximum)}`;
}

function CostImpactChip({ costImpact, compact }: { costImpact: CostImpactRange; compact: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full bg-emerald-500/12 font-semibold leading-none text-emerald-700",
        compact ? "px-2 py-1 text-[10px]" : "px-3 py-1.5 text-[11px]",
      )}
    >
      Save {formatCurrencyRange(costImpact.minimum_unit_savings_eur, costImpact.maximum_unit_savings_eur)} / unit
    </span>
  );
}

function CostImpactSummaryRow({ costImpact }: { costImpact: CostImpactRange }) {
  return (
    <div className="grid grid-cols-[auto_1fr] items-start gap-3 rounded-[14px] border border-emerald-500/12 bg-emerald-500/[0.03] px-3 py-2.5">
      <CostImpactChip costImpact={costImpact} compact={false} />
      <div className="min-w-0 space-y-1 pt-0.5">
        <p className="text-[12px] leading-5 text-[var(--panel-muted)]">{costImpact.rationale}</p>
        <p className="text-[11px] leading-4 text-[var(--panel-muted)]">
          {costImpact.conservative_label} to {costImpact.optimistic_label}
        </p>
      </div>
    </div>
  );
}

function CostImpactBreakdownRow({ row }: { row: CostImpactBreakdown }) {
  return (
    <div className="space-y-1">
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-semibold text-slate-800">{row.label}</span>
        <span className="text-xs font-semibold text-emerald-700">
          {formatCurrencyRange(row.minimum_unit_savings_eur, row.maximum_unit_savings_eur)}
        </span>
      </div>
      {row.details ? <p className="text-[11px] text-[var(--panel-muted)]">{row.details}</p> : null}
    </div>
  );
}

function CostImpactBreakdownSection({ costImpact }: { costImpact: CostImpactRange }) {
  return (
    <div className="space-y-3 rounded-[16px] border border-[color:rgba(15,86,216,0.18)] bg-[color:rgba(15,86,216,0.06)] p-4">
      <Label className="text-[var(--accent)]">Cost Impact</Label>
      <div className="grid gap-4 sm:grid-cols-2">
        {smallStat("Baseline (Qty 1)", formatCurrency(costImpact.current_unit_cost_eur))}
        {smallStat("Unit Save", formatCurrencyRange(costImpact.minimum_unit_savings_eur, costImpact.maximum_unit_savings_eur))}
      </div>
      <p className="text-xs text-[var(--panel-muted)]">{costImpact.rationale}</p>
      <p className="text-xs text-[var(--panel-muted)]">
        Range: {costImpact.conservative_label} to {costImpact.optimistic_label}
      </p>

      {costImpact.direct_breakdown.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-800">Direct</h4>
          <div className="space-y-2">
            {costImpact.direct_breakdown.map((row, index) => (
              <CostImpactBreakdownRow key={`${row.label}-${index}`} row={row} />
            ))}
          </div>
        </div>
      ) : null}

      {costImpact.linked_breakdown.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-800">Linked</h4>
          <div className="space-y-2">
            {costImpact.linked_breakdown.map((row, index) => (
              <CostImpactBreakdownRow key={`${row.label}-${index}`} row={row} />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function CncDfmWorkbench() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedScreen, setSelectedScreen] = useState<SidebarScreen>("recommendations");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [materials, setMaterials] = useState<MaterialSpec[]>([]);
  const [savedConfig, setSavedConfig] = useState<ConfigValues | null>(null);
  const [configDraft, setConfigDraft] = useState<ConfigValues | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [selectedRecommendationId, setSelectedRecommendationId] = useState<string | null>(null);
  const [selectedFeatureGroupId, setSelectedFeatureGroupId] = useState<string | null>(null);
  const [selectedFeatureInstanceId, setSelectedFeatureInstanceId] = useState<string | null>(null);
  const [lastErrorMessage, setLastErrorMessage] = useState<string | null>(null);
  const [pendingAnalysisFileName, setPendingAnalysisFileName] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isPending, startTransition] = useTransition();
  const deferredFocusedInsightId = useDeferredValue(selectedFeatureInstanceId);
  const isAnalysisScreen = selectedScreen === "recommendations" || selectedScreen === "ruleResults" || selectedScreen === "summary";

  async function bootstrap() {
    setIsBootstrapping(true);
    try {
      const [nextHealth, nextConfig, nextMaterials] = await Promise.all([
        fetchHealth(),
        fetchConfig(),
        fetchMaterials(),
      ]);
      startTransition(() => {
        setHealth(nextHealth);
        setSavedConfig(nextConfig.values);
        setConfigDraft(nextConfig.values);
        setMaterials(nextMaterials.materials);
        setLastErrorMessage(null);
      });
    } catch (error) {
      setLastErrorMessage(error instanceof Error ? error.message : "Unable to bootstrap web app.");
    } finally {
      setIsBootstrapping(false);
    }
  }

  async function refreshDiagnostics() {
    try {
      const nextHealth = await fetchHealth();
      startTransition(() => {
        setHealth(nextHealth);
        setLastErrorMessage(null);
      });
    } catch (error) {
      setLastErrorMessage(error instanceof Error ? error.message : "Unable to refresh diagnostics.");
    }
  }

  useEffect(() => {
    let active = true;

    async function runBootstrap() {
      if (!active) {
        return;
      }
      await bootstrap();
    }

    runBootstrap();
    return () => {
      active = false;
    };
  }, []);

  const selectedRecommendation = analysis?.recommendations.find((item) => item.title + item.source + item.kind === selectedRecommendationId) ?? analysis?.recommendations[0] ?? null;
  const featureGroups = groupFeatureInsights(selectedRecommendation);
  const focusedFeatureInsight = focusInsight(selectedRecommendation, selectedFeatureInstanceId);
  const displayedProcessData = analysis && (configDraft ?? savedConfig)
    ? applyQuantityToProcessData(
        analysis.process_data,
        quantity,
        configDraft?.qty_learning_rate ?? savedConfig?.qty_learning_rate ?? 0.76,
        configDraft?.qty_factor_floor ?? savedConfig?.qty_factor_floor ?? 0.29,
      )
    : null;

  function selectRecommendation(recommendation: Recommendation) {
    const nextId = recommendation.title + recommendation.source + recommendation.kind;
    setSelectedRecommendationId(nextId);
    const groups = groupFeatureInsights(recommendation);
    setSelectedFeatureGroupId(groups[0]?.id ?? null);
    setSelectedFeatureInstanceId(groups[0]?.instances[0]?.id ?? null);
  }

  function selectFeatureGroup(groupId: string) {
    const group = featureGroups.find((item) => item.id === groupId);
    setSelectedFeatureGroupId(groupId);
    setSelectedFeatureInstanceId(group?.instances[0]?.id ?? null);
  }

  function stepFeature(groupId: string, delta: number) {
    const group = featureGroups.find((item) => item.id === groupId);
    if (!group || group.instances.length === 0) {
      return;
    }
    const currentIndex = group.instances.findIndex((item) => item.id === selectedFeatureInstanceId);
    const baseIndex = currentIndex < 0 ? 0 : currentIndex;
    const nextIndex = (baseIndex + delta + group.instances.length) % group.instances.length;
    setSelectedFeatureGroupId(group.id);
    setSelectedFeatureInstanceId(group.instances[nextIndex]?.id ?? null);
  }

  function onPickFile() {
    fileInputRef.current?.click();
  }

  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setSelectedFile(file);
    await runAnalysis(file);
  }

  async function runAnalysis(file?: File) {
    const nextFile = file ?? selectedFile;
    if (!nextFile) {
      setLastErrorMessage("Select a STEP file before running analysis.");
      return;
    }

    setPendingAnalysisFileName(nextFile.name);
    setIsAnalyzing(true);
    try {
      const response = await analyzeFile(nextFile, quantity);
      const defaultRecommendation = response.analysis.recommendations[0] ?? null;
      const defaultGroups = groupFeatureInsights(defaultRecommendation);
      startTransition(() => {
        setAnalysis(response.analysis);
        setPreviewUrl(resolveArtifactUrl(response.previewUrl));
        setQuantity(response.analysis.process_data.qty);
        setSelectedRecommendationId(defaultRecommendation ? defaultRecommendation.title + defaultRecommendation.source + defaultRecommendation.kind : null);
        setSelectedFeatureGroupId(defaultGroups[0]?.id ?? null);
        setSelectedFeatureInstanceId(defaultGroups[0]?.instances[0]?.id ?? null);
        setLastErrorMessage(null);
        setSelectedScreen("recommendations");
      });
    } catch (error) {
      setLastErrorMessage(error instanceof Error ? error.message : "Analysis failed.");
    } finally {
      setIsAnalyzing(false);
      setPendingAnalysisFileName(null);
    }
  }

  async function persistConfig() {
    if (!configDraft) {
      return;
    }
    setIsSavingSettings(true);
    try {
      const response = await saveConfig(configDraft);
      const nextHealth = await fetchHealth();
      startTransition(() => {
        setSavedConfig(response.values);
        setConfigDraft(response.values);
        setHealth(nextHealth);
        setLastErrorMessage(null);
      });
    } catch (error) {
      setLastErrorMessage(error instanceof Error ? error.message : "Failed to save settings.");
    } finally {
      setIsSavingSettings(false);
    }
  }

  function updateConfigValue(field: ConfigField, value: string) {
    if (!configDraft) {
      return;
    }
    const parsed = field.type === "integer" ? Number.parseInt(value, 10) : Number.parseFloat(value);
    if (!Number.isFinite(parsed)) {
      setConfigDraft({
        ...configDraft,
        [field.key]: 0,
      } as ConfigValues);
      return;
    }
    setConfigDraft({
      ...configDraft,
      [field.key]: parsed,
    } as ConfigValues);
  }

  function renderPreviewPanel() {
    if (previewUrl) {
      return (
        <div className="fine-grid aspect-square min-h-[420px] overflow-hidden rounded-[20px] border border-[color:var(--panel-border)] bg-[linear-gradient(180deg,#edf2fb_0%,#dfe7f6_100%)] shadow-[var(--ring-shadow)]">
          <DynamicPartPreview
            previewUrl={previewUrl}
            highlightedInsights={selectedRecommendation?.feature_insights ?? []}
            focusedInsightId={deferredFocusedInsightId ?? null}
          />
        </div>
      );
    }

    return (
      <Card>
        <CardHeader>
          <CardTitle>3D Preview</CardTitle>
          <CardDescription>Preview appears here after analysis finishes.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex min-h-[320px] items-center justify-center rounded-[20px] border border-dashed border-[color:var(--panel-border)] bg-white/50 text-center text-sm text-[var(--panel-muted)]">
            {isAnalyzing ? "Generating preview from the uploaded STEP file..." : "Run an analysis to load the model preview."}
          </div>
        </CardContent>
      </Card>
    );
  }

  function renderRecommendations() {
    return (
      <Card className="section-fade">
        <CardHeader>
          <CardTitle>Recommendations</CardTitle>
          <CardDescription>
            {analysis?.recommendations[0]?.kind === "blocker"
              ? "Fix blockers first, then reduce cost drivers."
              : "Prioritized design guidance from the shared Python analysis."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {analysis?.recommendations.map((recommendation, index) => {
            const recommendationId = recommendation.title + recommendation.source + recommendation.kind;
            const isSelected = selectedRecommendationId ? selectedRecommendationId === recommendationId : index === 0;
            const groups = groupFeatureInsights(recommendation);

            return (
              <div
                key={recommendationId}
                className={cn(
                  "cursor-pointer rounded-[20px] border p-4 transition",
                  isSelected
                    ? "border-[color:rgba(15,86,216,0.34)] bg-[var(--accent-soft)]"
                    : "border-[color:var(--panel-border)] bg-white/58 hover:bg-white/76",
                )}
                onClick={() => selectRecommendation(recommendation)}
              >
                <div className="w-full space-y-4 text-left">
                  <div className="flex items-start gap-3">
                    <Badge tone={recommendationTone(recommendation.kind)}>{recommendationLabel(recommendation.kind)}</Badge>
                    <div className="flex-1">
                      <h3 className="text-base font-semibold tracking-[-0.02em]">{recommendation.title}</h3>
                      <p className="mt-1 text-sm text-slate-700">{recommendation.summary}</p>
                    </div>
                    <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs font-semibold text-[var(--panel-muted)]">
                      P{recommendation.priority}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--panel-muted)]">{recommendation.impact}</p>
                  {recommendation.cost_impact ? <CostImpactSummaryRow costImpact={recommendation.cost_impact} /> : null}
                </div>

                {isSelected && groups.length > 0 ? (
                  <div className="mt-4 space-y-3 rounded-[18px] border border-[color:rgba(15,86,216,0.2)] bg-white/72 p-4">
                    <div className="flex items-center justify-between">
                      <Label className="text-[var(--accent)]">Where</Label>
                      {focusedFeatureInsight?.units ? (
                        <span className="text-xs font-medium text-[var(--panel-muted)]">
                          {focusedFeatureInsight.measured_value != null ? formatNumber(focusedFeatureInsight.measured_value) : "n/a"}
                          {focusedFeatureInsight.units ? ` ${focusedFeatureInsight.units}` : ""}
                        </span>
                      ) : null}
                    </div>
                    {groups.map((group) => {
                      const selected = selectedFeatureGroupId ? selectedFeatureGroupId === group.id : groups[0]?.id === group.id;
                      const currentIndex = Math.max(0, group.instances.findIndex((item) => item.id === selectedFeatureInstanceId));
                      const currentImpact =
                        group.instances[currentIndex]?.cost_impact ??
                        group.instances.find((item) => item.cost_impact)?.cost_impact;

                      return (
                        <div
                          key={group.id}
                          className={cn(
                            "rounded-2xl border p-3",
                            selected
                              ? "border-[color:rgba(15,86,216,0.34)] bg-[var(--accent-soft)]"
                              : "border-[color:var(--panel-border)] bg-white/78",
                          )}
                        >
                          <button
                            className="flex w-full items-start gap-3 text-left"
                            onClick={(event) => {
                              event.stopPropagation();
                              selectFeatureGroup(group.id);
                            }}
                          >
                            <span className="mt-0.5 text-xs font-semibold text-[var(--accent)]">{selected ? "◎" : "○"}</span>
                            <span className="flex-1 text-sm">{group.instances.length > 1 ? `x${group.instances.length} ${group.summary}` : group.summary}</span>
                            {currentImpact ? <CostImpactChip costImpact={currentImpact} compact /> : null}
                          </button>
                          {selected && group.instances.length > 1 ? (
                            <div className="mt-3 flex items-center gap-3">
                              <Button
                                className="h-9 w-9 px-0"
                                variant="outline"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  stepFeature(group.id, -1);
                                }}
                              >
                                ←
                              </Button>
                              <span className="text-xs font-semibold tracking-[0.18em] text-[var(--panel-muted)]">
                                {currentIndex + 1} / {group.instances.length}
                              </span>
                              <Button
                                className="h-9 w-9 px-0"
                                variant="outline"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  stepFeature(group.id, 1);
                                }}
                              >
                                →
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : null}

                {isSelected && recommendation.cost_impact ? (
                  <div className="mt-4">
                    <CostImpactBreakdownSection costImpact={recommendation.cost_impact} />
                  </div>
                ) : null}

                <div className="mt-4 space-y-2">
                  {recommendation.actions.map((action) => (
                    <div key={action} className="flex gap-3 text-sm text-slate-700">
                      <span className="text-[var(--accent)]">-</span>
                      <span>{action}</span>
                    </div>
                  ))}
                </div>

                <p className="mt-4 text-xs uppercase tracking-[0.18em] text-[var(--panel-muted)]">Source: {recommendation.source}</p>
                {isSelected && recommendation.cost_impact ? (
                  <p className="mt-3 text-xs text-[var(--panel-muted)]">
                    Savings are independent unit what-if estimates against a fixed qty-1 baseline. They do not live-update
                    with Summary tab quantity, and recommendation ranges should not be added together.
                  </p>
                ) : null}
              </div>
            );
          })}
        </CardContent>
      </Card>
    );
  }

  function renderRuleResults() {
    return (
      <Card className="section-fade">
        <CardHeader>
          <CardTitle>Rule Results</CardTitle>
          <CardDescription>{analysis?.rules.length ?? 0} evaluated</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {analysis?.rules.map((rule) => {
            const metric = metricBarData(rule);
            return (
              <div key={rule.name} className="rounded-[20px] border border-[color:var(--panel-border)] bg-white/60 p-4">
                <div className="flex items-center gap-3">
                  <span className={cn("h-2.5 w-2.5 rounded-full", rule.passed ? "bg-[var(--success)]" : "bg-[var(--danger)]")} />
                  <h3 className="text-base font-semibold tracking-[-0.02em]">{rule.name}</h3>
                  <span className={cn("ml-auto text-xs font-semibold tracking-[0.18em]", rule.passed ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                    {rule.passed ? "PASS" : "FAIL"}
                  </span>
                </div>
                <p className="mt-3 text-sm font-medium text-slate-700">{rule.summary}</p>
                <p className="mt-1 text-sm text-[var(--panel-muted)]">{rule.details}</p>

                {metric ? (
                  <div className="mt-4 rounded-[18px] bg-slate-50/80 p-4">
                    <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.18em] text-[var(--panel-muted)]">
                      <span>Metric Bar</span>
                      <span>{metric.legend}</span>
                    </div>
                    <div className="relative mt-4 h-7">
                      <div className="absolute inset-x-0 top-2 h-2 rounded-full bg-slate-200" />
                      <div className="absolute top-0 h-6 w-6 -translate-x-1/2 rounded-full bg-[var(--accent)] text-center text-[10px] font-bold leading-6 text-white" style={{ left: `${metric.thresholdPosition * 100}%` }}>
                        T
                      </div>
                      <div className={cn("absolute top-0 h-6 w-6 -translate-x-1/2 rounded-full text-center text-[10px] font-bold leading-6 text-white", rule.passed ? "bg-[var(--success)]" : "bg-[var(--danger)]")} style={{ left: `${metric.averagePosition * 100}%` }}>
                        A
                      </div>
                    </div>
                    <p className="mt-3 font-mono text-xs text-[var(--panel-muted)]">{metric.metricLine}</p>
                  </div>
                ) : null}

                <div className="mt-4 grid gap-3 sm:grid-cols-4">
                  {keyValueRows([
                    { label: "Detected", value: formatInteger(rule.detected_features) },
                    { label: "Pass", value: formatInteger(rule.passed_features) },
                    { label: "Fail", value: formatInteger(rule.failed_features) },
                    { label: "Multiplier", value: formatMultiplier(rule.rule_multiplier) },
                  ])}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>
    );
  }

  function renderSummary() {
    if (!analysis || !displayedProcessData) {
      return null;
    }

    return (
      <div className="section-fade space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Unit Estimate</CardTitle>
            <CardDescription>Current cost per unit in the active analysis. Recommendation savings use a fixed qty-1 baseline.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-[38px] font-bold tracking-[-0.04em] text-slate-900">
              {formatCurrency(displayedProcessData.total_estimated_cost_eur)}
            </div>
            <div className="flex flex-wrap gap-8">
              {smallStat("Batch", formatCurrency(displayedProcessData.batch_total_estimated_cost_eur))}
              {smallStat("Qty", String(displayedProcessData.qty))}
              {smallStat("Machine", displayedProcessData.machine_type)}
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Overview</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              {keyValueRows([
                { label: "File", value: analysis.file_path },
                { label: "Rules Passed", value: `${analysis.summary.passed_rule_count} / ${analysis.summary.total_rule_count}` },
                { label: "Rule Multiplier", value: formatMultiplier(analysis.summary.rule_multiplier) },
                { label: "Status", value: analysis.summary.passed ? "All active rules passed" : `${analysis.summary.failed_rule_count} rule(s) failed` },
              ])}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Current Top Recommendation</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis.recommendations[0] ? (
                <>
                  <Badge tone={recommendationTone(analysis.recommendations[0].kind)}>{recommendationLabel(analysis.recommendations[0].kind)}</Badge>
                  <h3 className="text-lg font-semibold tracking-[-0.02em]">{analysis.recommendations[0].title}</h3>
                  <p className="text-sm text-[var(--panel-muted)]">{analysis.recommendations[0].summary}</p>
                </>
              ) : (
                <p className="text-sm text-[var(--panel-muted)]">No recommendation available.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Part Facts</CardTitle>
            <CardDescription>{displayedProcessData.material_label}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {keyValueRows([
              { label: "Material", value: displayedProcessData.material_label },
              { label: "Machine Type", value: displayedProcessData.machine_type },
              { label: "Part BBox", value: `${formatNumber(displayedProcessData.part_bbox_x_mm)} x ${formatNumber(displayedProcessData.part_bbox_y_mm)} x ${formatNumber(displayedProcessData.part_bbox_z_mm)} mm` },
              { label: "Stock BBox", value: `${formatNumber(displayedProcessData.stock_bbox_x_mm)} x ${formatNumber(displayedProcessData.stock_bbox_y_mm)} x ${formatNumber(displayedProcessData.stock_bbox_z_mm)} mm` },
              { label: "Volume", value: `${formatNumber(displayedProcessData.volume_mm3)} mm³` },
              { label: "Removed Volume", value: `${formatNumber(displayedProcessData.removed_volume_mm3)} mm³` },
              { label: "Mass", value: `${formatNumber(displayedProcessData.mass_kg)} kg` },
              { label: "Setup Directions", value: displayedProcessData.required_setup_directions },
            ])}
            <div className="rounded-2xl bg-white/55 px-4 py-3">
              <Label htmlFor="quantity">Quantity</Label>
              <div className="mt-3 flex items-center gap-3">
                <Button className="h-10 w-10 px-0" variant="outline" onClick={() => setQuantity((current) => Math.max(1, current - 1))}>
                  -
                </Button>
                <Input
                  id="quantity"
                  className="w-28"
                  inputMode="numeric"
                  min={1}
                  type="number"
                  value={quantity}
                  onChange={(event) => setQuantity(Math.max(1, Number.parseInt(event.target.value || "1", 10)))}
                />
                <Button className="h-10 w-10 px-0" variant="outline" onClick={() => setQuantity((current) => current + 1)}>
                  +
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pre-Multiplier Drivers</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {keyValueRows([
              { label: "Surface Area Ratio", value: formatMultiplier(displayedProcessData.surface_area_ratio) },
              { label: "Surface Complexity", value: `${formatInteger(displayedProcessData.surface_complexity_faces)} faces` },
              { label: "Hole Count", value: formatInteger(displayedProcessData.hole_count) },
              { label: "Radius Count", value: formatInteger(displayedProcessData.radius_count) },
              { label: "Machinability Index", value: formatNumber(displayedProcessData.machinability_index) },
              { label: "Estimated Roughing MRR", value: `${formatNumber(displayedProcessData.estimated_roughing_mrr_mm3_per_min)} mm³/min` },
            ])}
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Multipliers</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              {keyValueRows([
                { label: "Surface Area", value: formatMultiplier(displayedProcessData.surface_area_multiplier) },
                { label: "Complexity", value: formatMultiplier(displayedProcessData.complexity_multiplier) },
                { label: "Hole Count", value: formatMultiplier(displayedProcessData.hole_count_multiplier) },
                { label: "Radius Count", value: formatMultiplier(displayedProcessData.radius_count_multiplier) },
                { label: "Material", value: formatMultiplier(displayedProcessData.material_time_multiplier) },
                { label: "Rule", value: formatMultiplier(displayedProcessData.rule_multiplier) },
                { label: "Total Time", value: formatMultiplier(displayedProcessData.total_time_multiplier) },
                { label: "Qty", value: formatMultiplier(displayedProcessData.qty_multiplier) },
              ])}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Costs</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              {keyValueRows([
                { label: "Material Total", value: formatCurrency(displayedProcessData.material_stock_cost_eur) },
                { label: "Roughing Cost", value: formatCurrency(displayedProcessData.roughing_cost) },
                { label: "Machining Cost", value: formatCurrency(displayedProcessData.machining_cost) },
                { label: "Unit Estimate", value: formatCurrency(displayedProcessData.total_estimated_cost_eur) },
                { label: "Batch Estimate", value: formatCurrency(displayedProcessData.batch_total_estimated_cost_eur) },
                { label: "Machine Rate", value: formatCurrency(displayedProcessData.machine_hourly_rate_eur) },
              ])}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  function renderSettings() {
    return (
      <div className="section-fade space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Shared Config</CardTitle>
            <CardDescription>These values write to the same backend config used by the CLI.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={bootstrap}>
              Reload
            </Button>
            <Button
              disabled={!savedConfig || !configDraft || JSON.stringify(savedConfig) === JSON.stringify(configDraft)}
              variant="outline"
              onClick={() => savedConfig && setConfigDraft(savedConfig)}
            >
              Reset Changes
            </Button>
            <div className="ml-auto">
              <Button disabled={!configDraft || isSavingSettings} onClick={persistConfig}>
                {isSavingSettings ? "Saving..." : "Save Settings"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {configDraft ? (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Rule Thresholds</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-2">
                {configSections[0].fields.map((field) => (
                  <div key={field.key} className="space-y-2">
                    <Label htmlFor={field.key}>{field.label}</Label>
                    <Input
                      id={field.key}
                      step={field.step}
                      type="number"
                      value={String(configDraft[field.key])}
                      onChange={(event) => updateConfigValue(field, event.target.value)}
                    />
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Material And Machine</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="material">Material</Label>
                  <select
                    id="material"
                    className="w-full rounded-xl border border-[color:var(--panel-border)] bg-white/80 px-3 py-2.5 text-sm outline-none focus:border-[var(--accent)]"
                    value={configDraft.material}
                    onChange={(event) => setConfigDraft({ ...configDraft, material: event.target.value } as ConfigValues)}
                  >
                    {materials.map((material) => (
                      <option key={material.key} value={material.key}>
                        {material.label}
                      </option>
                    ))}
                  </select>
                </div>
                {configSections[1].fields.map((field) => (
                  <div key={field.key} className="space-y-2">
                    <Label htmlFor={field.key}>{field.label}</Label>
                    <Input
                      id={field.key}
                      step={field.step}
                      type="number"
                      value={String(configDraft[field.key])}
                      onChange={(event) => updateConfigValue(field, event.target.value)}
                    />
                  </div>
                ))}
                <div className="space-y-2">
                  <Label htmlFor="surface_penalty_slope">Surface Penalty Slope</Label>
                  <Input
                    id="surface_penalty_slope"
                    step="0.001"
                    type="number"
                    value={String(configDraft.surface_penalty_slope)}
                    onChange={(event) => updateConfigValue({ key: "surface_penalty_slope", label: "", description: "", type: "number", step: "0.001" }, event.target.value)}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Multiplier Controls</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-2">
                {configSections[2].fields.map((field) => (
                  <div key={field.key} className="space-y-2">
                    <Label htmlFor={field.key}>{field.label}</Label>
                    <Input
                      id={field.key}
                      step={field.step}
                      type="number"
                      value={String(configDraft[field.key])}
                      onChange={(event) => updateConfigValue(field, event.target.value)}
                    />
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Current Selection</CardTitle>
                <CardDescription>Saved config path and material baseline context.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {keyValueRows([
                  { label: "Config Path", value: health?.configPath ?? "Unavailable" },
                  { label: "Material", value: materials.find((item) => item.key === configDraft.material)?.label ?? "Unavailable" },
                  { label: "Machinability Source", value: materials.find((item) => item.key === configDraft.material)?.machinability_source ?? "Unavailable" },
                  { label: "Billet Cost Source", value: materials.find((item) => item.key === configDraft.material)?.baseline_billet_cost_source ?? "Unavailable" },
                ])}
              </CardContent>
            </Card>
          </>
        ) : (
          <Card>
            <CardContent className="py-14 text-center text-sm text-[var(--panel-muted)]">Loading config...</CardContent>
          </Card>
        )}
      </div>
    );
  }

  function renderDiagnostics() {
    return (
      <div className="section-fade space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Backend Status</CardTitle>
            <CardDescription>What the app is launching right now.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <span className={cn("h-2.5 w-2.5 rounded-full", health?.analysisRuntime.available ? "bg-[var(--success)]" : "bg-[var(--warning)]")} />
              <span className="text-base font-semibold">
                {health?.analysisRuntime.available ? "Analysis runtime available" : "Analysis runtime unavailable"}
              </span>
            </div>
            <div className="space-y-3">
              {keyValueRows([
                { label: "Python", value: health?.pythonExecutable ?? "Unavailable" },
                { label: "Config Path", value: health?.configPath ?? "Unavailable" },
                { label: "Platform", value: health?.platform ?? "Unavailable" },
                { label: "Working Directory", value: health?.cwd ?? "Unavailable" },
              ])}
            </div>
          </CardContent>
        </Card>

        {health?.analysisRuntime.available === false ? (
          <Card>
            <CardHeader>
              <CardTitle>Runtime Error</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {keyValueRows([
                { label: "Error Type", value: health.analysisRuntime.errorType ?? "Unknown" },
                { label: "Message", value: health.analysisRuntime.message ?? "Unknown backend startup error." },
              ])}
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Health Payload</CardTitle>
            <CardDescription>Direct backend status for app diagnostics.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {keyValueRows([
              { label: "Status", value: health?.status ?? "Unavailable" },
              { label: "API Version", value: health ? String(health.apiVersion) : "Unavailable" },
              { label: "Allowed Origins", value: health?.webApi?.origins?.join(", ") ?? "Unavailable" },
            ])}
          </CardContent>
        </Card>

        <div className="flex">
          <Button onClick={refreshDiagnostics}>Refresh Diagnostics</Button>
        </div>
      </div>
    );
  }

  function renderActiveScreen() {
    if (!analysis && ["recommendations", "ruleResults", "summary"].includes(selectedScreen)) {
      return (
        <Card className="section-fade">
          <CardHeader>
            <CardTitle>
              {selectedScreen === "recommendations"
                ? "No Recommendations Yet"
                : selectedScreen === "ruleResults"
                  ? "No Rule Results Yet"
                  : "No Analysis Summary Yet"}
            </CardTitle>
            <CardDescription>Upload a STEP file to run the shared backend analysis.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex min-h-[260px] items-center justify-center rounded-[20px] border border-dashed border-[color:var(--panel-border)] bg-white/48 text-center text-sm text-[var(--panel-muted)]">
              Choose a STEP file in the sidebar to start the next run.
            </div>
          </CardContent>
        </Card>
      );
    }

    switch (selectedScreen) {
      case "recommendations":
        return renderRecommendations();
      case "ruleResults":
        return renderRuleResults();
      case "summary":
        return renderSummary();
      case "settings":
        return renderSettings();
      case "diagnostics":
        return renderDiagnostics();
      default:
        return null;
    }
  }

  return (
    <div className="min-h-screen px-4 py-4 sm:px-6 sm:py-6 lg:h-[100dvh] lg:overflow-hidden">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 lg:h-full lg:flex-row">
        <aside className="w-full lg:flex lg:h-full lg:max-w-[272px] lg:flex-col">
          <Card className="overflow-hidden">
            <CardContent className="space-y-4">
              <input
                ref={fileInputRef}
                accept=".step,.stp"
                className="hidden"
                type="file"
                onChange={onFileChange}
              />

              <button
                className="w-full rounded-[20px] border border-[color:var(--panel-border)] bg-white/75 px-4 py-5 text-center transition hover:bg-white"
                onClick={onPickFile}
              >
                <div className="flex justify-center">
                  <NewAnalysisIcon />
                </div>
                <div className="mt-3 space-y-1">
                  <h2 className="text-base font-semibold">Run New Analysis</h2>
                  <p className="text-sm text-[var(--panel-muted)]">
                    {pendingAnalysisFileName
                      ? `Loading ${pendingAnalysisFileName}`
                      : isBootstrapping
                        ? "Loading backend state"
                        : "Choose a STEP file and start the next run."}
                  </p>
                </div>
              </button>

              <div className="space-y-2">
                {outputScreens.map((screen) => (
                  <button
                    key={screen.id}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition",
                      selectedScreen === screen.id
                        ? "bg-[color:rgba(15,86,216,0.12)] text-[var(--page-ink)]"
                        : "text-slate-700 hover:bg-white/75",
                    )}
                    onClick={() => startTransition(() => setSelectedScreen(screen.id))}
                  >
                    <span className="flex w-5 items-center justify-center">
                      <SidebarIcon active={selectedScreen === screen.id} name={screen.id} />
                    </span>
                    <span className="font-medium">{screen.title}</span>
                  </button>
                ))}
              </div>

              <Separator />

              <div className="space-y-2">
                {utilityScreens.map((screen) => (
                  <button
                    key={screen.id}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition",
                      selectedScreen === screen.id
                        ? "bg-[color:rgba(15,86,216,0.12)] text-[var(--page-ink)]"
                        : "text-slate-700 hover:bg-white/75",
                    )}
                    onClick={() => startTransition(() => setSelectedScreen(screen.id))}
                  >
                    <span className="flex w-5 items-center justify-center">
                      <SidebarIcon active={selectedScreen === screen.id} name={screen.id} />
                    </span>
                    <span className="font-medium">{screen.title}</span>
                  </button>
                ))}
              </div>

            </CardContent>
          </Card>
        </aside>

        <main className="min-w-0 flex-1 lg:min-h-0 lg:h-full">
          <div className="space-y-4 lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:overflow-hidden">
            {lastErrorMessage ? (
              <Card className="border-[color:rgba(180,35,24,0.2)] bg-[var(--danger-soft)]">
                <CardContent className="flex items-center gap-3 py-4">
                  <span className="text-lg text-[var(--danger)]">!</span>
                  <p className="flex-1 text-sm text-[var(--danger)]">{lastErrorMessage}</p>
                  <Button variant="ghost" onClick={() => setLastErrorMessage(null)}>
                    Dismiss
                  </Button>
                </CardContent>
              </Card>
            ) : null}

            {pendingAnalysisFileName && isAnalysisScreen ? (
              <Card>
                <CardHeader>
                  <CardTitle>Running New Analysis</CardTitle>
                  <CardDescription>The current results stay visible until the next run finishes.</CardDescription>
                </CardHeader>
                <CardContent className="flex items-center gap-4 pt-0">
                  <div className="h-10 w-10 rounded-full border-4 border-slate-300 border-t-slate-500 animate-spin" />
                  <div className="space-y-0.5">
                    <p className="text-sm font-semibold">{pendingAnalysisFileName}</p>
                    <p className="text-sm text-[var(--panel-muted)]">Loading next analysis in the background</p>
                  </div>
                </CardContent>
              </Card>
            ) : null}

            {isAnalysisScreen ? (
              <div className="grid gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1fr)_minmax(420px,48%)] lg:overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_560px]">
                <div className="min-w-0 lg:min-h-0 lg:h-full lg:overflow-y-auto lg:pr-2">{renderActiveScreen()}</div>
                <div className="min-w-0 lg:sticky lg:top-0 lg:self-start">{renderPreviewPanel()}</div>
              </div>
            ) : (
              <div className="max-w-[1120px] lg:min-h-0 lg:h-full lg:overflow-y-auto lg:pr-2">{renderActiveScreen()}</div>
            )}
          </div>
        </main>
      </div>
      {isPending ? <div className="pointer-events-none fixed inset-x-0 bottom-0 h-1 bg-[linear-gradient(90deg,transparent,rgba(15,86,216,0.7),transparent)]" /> : null}
    </div>
  );
}
