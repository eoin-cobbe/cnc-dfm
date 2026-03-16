import type {
  AnalyzeResponse,
  Analysis,
  AnalysisProgress,
  ConfigResponse,
  ConfigValues,
  FeatureInsight,
  HealthResponse,
  MaterialsResponse,
  PreviewResponse,
} from "@/lib/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_CNC_DFM_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function parseJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T & { error?: { message?: string } };
  if (!response.ok) {
    throw new Error(payload.error?.message ?? `Request failed with status ${response.status}`);
  }
  return payload;
}

function normalizeFeatureInsightArtifacts(insight: FeatureInsight): FeatureInsight {
  return {
    ...insight,
    overlay_mesh_paths: insight.overlay_mesh_paths.map((path) => resolveArtifactUrl(path) ?? path),
  };
}

function normalizeAnalysisArtifacts(analysis: Analysis): Analysis {
  return {
    ...analysis,
    recommendations: analysis.recommendations.map((recommendation) => ({
      ...recommendation,
      feature_insights: recommendation.feature_insights.map(normalizeFeatureInsightArtifacts),
    })),
  };
}

export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`, {
    cache: "no-store",
  });
  return parseJson<HealthResponse>(response);
}

export async function fetchConfig() {
  const response = await fetch(`${API_BASE_URL}/api/v1/config`, {
    cache: "no-store",
  });
  return parseJson<ConfigResponse>(response);
}

export async function fetchMaterials() {
  const response = await fetch(`${API_BASE_URL}/api/v1/materials`, {
    cache: "no-store",
  });
  return parseJson<MaterialsResponse>(response);
}

export async function saveConfig(values: ConfigValues) {
  const response = await fetch(`${API_BASE_URL}/api/v1/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(values),
  });
  return parseJson<ConfigResponse>(response);
}

export async function analyzeFile(file: File, qty: number) {
  const formData = new FormData();
  formData.set("file", file);
  formData.set("qty", String(Math.max(1, qty)));
  formData.set("generate_preview", "false");

  const response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
    method: "POST",
    body: formData,
  });
  const payload = await parseJson<AnalyzeResponse>(response);
  return {
    ...payload,
    analysis: normalizeAnalysisArtifacts(payload.analysis),
    previewUrl: resolveArtifactUrl(payload.previewUrl),
  };
}

export async function analyzeFileWithProgress(
  file: File,
  qty: number,
  onProgress: (progress: AnalysisProgress) => void,
) {
  const formData = new FormData();
  formData.set("file", file);
  formData.set("qty", String(Math.max(1, qty)));
  formData.set("generate_preview", "true");

  const response = await fetch(`${API_BASE_URL}/api/v1/analyze/stream`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const payload = (await response.json()) as { error?: { message?: string } };
    throw new Error(payload.error?.message ?? `Request failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Analysis stream did not return a response body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      const event = JSON.parse(trimmed) as
        | { event: "progress"; progress: AnalysisProgress }
        | { event: "result" } & AnalyzeResponse
        | { event: "error"; error: { message?: string } };

      if (event.event === "progress") {
        onProgress(event.progress);
        continue;
      }
      if (event.event === "error") {
        throw new Error(event.error.message ?? "Analysis failed.");
      }
      return {
        ...event,
        analysis: normalizeAnalysisArtifacts(event.analysis),
        previewUrl: resolveArtifactUrl(event.previewUrl),
      };
    }
  }

  throw new Error("Analysis stream ended before a result was returned.");
}

export async function generatePreview(file: File) {
  const formData = new FormData();
  formData.set("file", file);

  const response = await fetch(`${API_BASE_URL}/api/v1/preview`, {
    method: "POST",
    body: formData,
  });
  const payload = await parseJson<PreviewResponse>(response);
  return {
    ...payload,
    previewUrl: resolveArtifactUrl(payload.previewUrl),
  };
}

export function resolveArtifactUrl(path: string | null | undefined) {
  if (!path) {
    return null;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}
