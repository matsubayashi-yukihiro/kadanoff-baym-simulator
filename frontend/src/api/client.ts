import type {
  DecisionNoteCreate,
  DecisionNoteRecord,
  EvidenceBundleRecord,
  GreenFunctionCatalogResponse,
  GreenFunctionSliceResponse,
  MixedGreenFunctionCatalogResponse,
  MixedGreenFunctionSliceResponse,
  ObservableCatalogResponse,
  ObservableResponse,
  PresetListResponse,
  RunDetail,
  RunResearchMetadataPatch,
  RunSummary,
  SimulationConfigInput,
  StudyCreate,
  StudyRecord,
  ThermalBranchCatalogResponse,
  ThermalBranchSliceResponse,
} from "./types";

const API_ROOT = `${
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000"
}/api/v1`;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  const isJson = response.headers.get("content-type")?.includes("application/json") ?? false;
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    throw new ApiError(response.status, extractErrorMessage(payload, response.statusText));
  }

  return payload as T;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback || "request failed";
  }
  if ("detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
            return item.msg;
          }
          return "validation error";
        })
        .join(", ");
    }
  }
  if ("message" in payload && typeof payload.message === "string") {
    return payload.message;
  }
  return fallback || "request failed";
}

export function createRun(config: SimulationConfigInput): Promise<RunDetail> {
  return request<RunDetail>("/runs", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export function listRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/runs");
}

export function listPresets(): Promise<PresetListResponse> {
  return request<PresetListResponse>("/presets");
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}`);
}

export function cancelRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}/cancel`, {
    method: "POST",
  });
}

export function listObservables(runId: string): Promise<ObservableCatalogResponse> {
  return request<ObservableCatalogResponse>(`/runs/${runId}/observables`);
}

export function getObservable(runId: string, name: string): Promise<ObservableResponse> {
  return request<ObservableResponse>(`/runs/${runId}/observables/${name}`);
}

export function listGreenFunctions(runId: string): Promise<GreenFunctionCatalogResponse> {
  return request<GreenFunctionCatalogResponse>(`/runs/${runId}/green-functions`);
}

export function getGreenFunctionSlice(
  runId: string,
  component: string,
  params: {
    row_start: number;
    row_stop: number;
    col_start: number;
    col_stop: number;
    nambu_start: number;
    nambu_stop: number;
  },
): Promise<GreenFunctionSliceResponse> {
  const searchParams = new URLSearchParams(
    Object.entries(params).map(([key, value]) => [key, String(value)]),
  );
  return request<GreenFunctionSliceResponse>(`/runs/${runId}/green-functions/${component}?${searchParams.toString()}`);
}

export function listThermalBranch(runId: string): Promise<ThermalBranchCatalogResponse> {
  return request<ThermalBranchCatalogResponse>(`/runs/${runId}/thermal-branch`);
}

export function getThermalBranchSlice(
  runId: string,
  component: string,
  params: {
    tau_start: number;
    tau_stop: number;
    nambu_start: number;
    nambu_stop: number;
  },
): Promise<ThermalBranchSliceResponse> {
  const searchParams = new URLSearchParams(
    Object.entries(params).map(([key, value]) => [key, String(value)]),
  );
  return request<ThermalBranchSliceResponse>(`/runs/${runId}/thermal-branch/${component}?${searchParams.toString()}`);
}

export async function getRunLog(runId: string): Promise<string> {
  const response = await fetch(`${API_ROOT}/runs/${runId}/log`);
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText || "failed to fetch log");
  }
  return response.text();
}

export function listMixedGreenFunctions(runId: string): Promise<MixedGreenFunctionCatalogResponse> {
  return request<MixedGreenFunctionCatalogResponse>(`/runs/${runId}/mixed-green-functions`);
}

export function listStudies(): Promise<StudyRecord[]> {
  return request<StudyRecord[]>("/studies");
}

export function createStudy(data: StudyCreate): Promise<StudyRecord> {
  return request<StudyRecord>("/studies", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listDecisionNotes(params: {
  study_id?: string;
  source_kind?: string;
  source_id?: string;
}): Promise<DecisionNoteRecord[]> {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null) as [string, string][],
  );
  return request<DecisionNoteRecord[]>(`/decision-notes${q.size ? "?" + q.toString() : ""}`);
}

export function createDecisionNote(data: DecisionNoteCreate): Promise<DecisionNoteRecord> {
  return request<DecisionNoteRecord>("/decision-notes", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listEvidenceBundles(params: { study_id?: string }): Promise<EvidenceBundleRecord[]> {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null) as [string, string][],
  );
  return request<EvidenceBundleRecord[]>(`/evidence-bundles${q.size ? "?" + q.toString() : ""}`);
}

export function patchRunMetadata(runId: string, patch: RunResearchMetadataPatch): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}/metadata`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function getMixedGreenFunctionSlice(
  runId: string,
  component: string,
  params: {
    time_start: number;
    time_stop: number;
    tau_start: number;
    tau_stop: number;
    nambu_start: number;
    nambu_stop: number;
  },
): Promise<MixedGreenFunctionSliceResponse> {
  const searchParams = new URLSearchParams(
    Object.entries(params).map(([key, value]) => [key, String(value)]),
  );
  return request<MixedGreenFunctionSliceResponse>(
    `/runs/${runId}/mixed-green-functions/${component}?${searchParams.toString()}`,
  );
}
