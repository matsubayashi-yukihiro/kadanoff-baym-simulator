import type {
  DecisionNoteCreate,
  DecisionNoteRecord,
  DerivedAnalysisArtifactRecord,
  DerivedAnalysisLaunchRequest,
  DerivedAnalysisResultRecord,
  DerivedAnalysisSourceKind,
  EvidenceBundlePatch,
  EvidenceBundleRecord,
  EvidenceBundleResolvedRecord,
  EvidenceBundleStatus,
  GreenFunctionCatalogResponse,
  GreenFunctionSliceResponse,
  KSpaceNativeCatalogResponse,
  KSpaceNativeLesserSliceResponse,
  JobGroupLaunchRequest,
  JobGroupRecord,
  MixedGreenFunctionCatalogResponse,
  MixedGreenFunctionSliceResponse,
  ObservableCatalogResponse,
  ObservableResponse,
  PresetListResponse,
  RunDetail,
  RunProgressRecord,
  RunResearchMetadataPatch,
  RunSummary,
  SimulationConfigInput,
  StudyCreate,
  StudyRecord,
  SweepLaunchRequest,
  SweepRecord,
  ThermalBranchCatalogResponse,
  ThermalBranchSliceResponse,
} from "./types";

const API_ROOT = `${
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000"
}/api/v1`;
const OPENAPI_URL = `${API_ROOT.replace(/\/api\/v1$/, "")}/openapi.json`;

export type BackendCapabilities = {
  supportsEquilibriumPayload: boolean;
  supportsDerivedAnalysisLaunch: boolean;
  supportsDerivedAnalysisRunKspace: boolean;
};

const DEFAULT_BACKEND_CAPABILITIES: BackendCapabilities = {
  supportsEquilibriumPayload: true,
  supportsDerivedAnalysisLaunch: true,
  supportsDerivedAnalysisRunKspace: true,
};

let backendCapabilitiesPromise: Promise<BackendCapabilities> | null = null;

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(status: number, message: string, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function getDefaultBackendCapabilities(): BackendCapabilities {
  return { ...DEFAULT_BACKEND_CAPABILITIES };
}

export async function getBackendCapabilities(forceRefresh = false): Promise<BackendCapabilities> {
  if (forceRefresh || backendCapabilitiesPromise === null) {
    backendCapabilitiesPromise = fetchBackendCapabilities();
  }
  return backendCapabilitiesPromise;
}

async function fetchBackendCapabilities(): Promise<BackendCapabilities> {
  try {
    const response = await fetch(OPENAPI_URL);
    if (!response.ok) return getDefaultBackendCapabilities();
    const spec = await response.json();
    return parseBackendCapabilities(spec);
  } catch {
    return getDefaultBackendCapabilities();
  }
}

function parseBackendCapabilities(spec: unknown): BackendCapabilities {
  if (!spec || typeof spec !== "object") {
    return getDefaultBackendCapabilities();
  }
  const root = spec as {
    paths?: Record<string, unknown>;
    components?: {
      schemas?: Record<string, { properties?: Record<string, unknown> }>;
    };
  };
  const schemas = root.components?.schemas ?? {};
  const simulationInput =
    schemas["SimulationConfig-Input"] ??
    schemas.SimulationConfig;
  const simulationProperties = simulationInput?.properties ?? {};
  const supportsEquilibriumPayload = "equilibrium" in simulationProperties;
  const supportsDerivedLaunchEndpoint = "/api/v1/derived-analyses/launch" in (root.paths ?? {});
  return {
    supportsEquilibriumPayload,
    supportsDerivedAnalysisLaunch: supportsDerivedLaunchEndpoint,
    supportsDerivedAnalysisRunKspace: supportsDerivedLaunchEndpoint && supportsEquilibriumPayload,
  };
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
    throw new ApiError(response.status, extractErrorMessage(payload, response.statusText), payload);
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
    if (detail && typeof detail === "object") {
      if ("message" in detail && typeof detail.message === "string") {
        if ("code" in detail && typeof detail.code === "string") {
          return `${detail.message} (${detail.code})`;
        }
        return detail.message;
      }
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (item && typeof item === "object") {
            const msg = "msg" in item && typeof item.msg === "string" ? item.msg : "validation error";
            const loc = Array.isArray(item.loc)
              ? item.loc
                .filter((part: unknown) => part !== "body")
                .map((part: unknown) => String(part))
                .join(".")
              : "";
            const input = "input" in item ? formatValidationInput(item.input) : "";
            return [loc ? `${loc}: ${msg}` : msg, input].filter(Boolean).join(" ");
          }
          return "validation error";
        })
        .join("\n");
    }
  }
  if ("message" in payload && typeof payload.message === "string") {
    return payload.message;
  }
  return fallback || "request failed";
}

function formatValidationInput(input: unknown): string {
  if (typeof input === "string") {
    return `(input=${JSON.stringify(input)})`;
  }
  if (typeof input === "number" || typeof input === "boolean") {
    return `(input=${String(input)})`;
  }
  if (input === null) {
    return "(input=null)";
  }
  if (Array.isArray(input)) {
    return `(input=${JSON.stringify(input)})`;
  }
  if (typeof input === "object") {
    const keys = Object.keys(input);
    return keys.length > 0 ? `(input keys: ${keys.join(", ")})` : "(input={})";
  }
  return "";
}

export function createRun(config: SimulationConfigInput): Promise<RunDetail> {
  return createRunWithCompatibilityFallback(config);
}

async function createRunWithCompatibilityFallback(config: SimulationConfigInput): Promise<RunDetail> {
  try {
    return await request<RunDetail>("/runs", {
      method: "POST",
      body: JSON.stringify(config),
    });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 422) {
      throw error;
    }

    const legacyCompatible = toLegacyCompatibleConfig(config, error.payload);
    if (legacyCompatible == null) {
      throw error;
    }

    return request<RunDetail>("/runs", {
      method: "POST",
      body: JSON.stringify(legacyCompatible),
    });
  }
}

function toLegacyCompatibleConfig(
  config: SimulationConfigInput,
  payload: unknown,
): SimulationConfigInput | null {
  const extraLocations = getExtraInputLocations(payload);
  const supportedCompatibilityLocations = new Set(["representation", "drive.drive_type", "equilibrium"]);

  if (extraLocations.length === 0) {
    return null;
  }
  if (extraLocations.some((loc) => !supportedCompatibilityLocations.has(loc))) {
    return null;
  }
  if (config.representation !== "real_space") {
    return null;
  }
  if (config.drive?.drive_type != null && config.drive.drive_type !== "gaussian") {
    return null;
  }

  const cloned = JSON.parse(JSON.stringify(config)) as Record<string, unknown>;
  delete cloned.representation;
  delete cloned.equilibrium;

  const drive = cloned.drive;
  if (typeof drive === "object" && drive !== null) {
    delete (drive as Record<string, unknown>).drive_type;
  }

  return cloned as SimulationConfigInput;
}

function getExtraInputLocations(payload: unknown): string[] {
  if (!payload || typeof payload !== "object" || !("detail" in payload) || !Array.isArray(payload.detail)) {
    return [];
  }

  return payload.detail
    .filter(
      (item): item is { loc?: unknown[]; msg?: string } =>
        !!item && typeof item === "object" && "msg" in item,
    )
    .filter((item) => item.msg === "Extra inputs are not permitted")
    .map((item) =>
      Array.isArray(item.loc)
        ? item.loc
          .filter((part: unknown) => part !== "body")
          .map((part: unknown) => String(part))
          .join(".")
        : "",
    )
    .filter((loc) => loc.length > 0);
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

export function getRunProgress(runId: string): Promise<RunProgressRecord> {
  return request<RunProgressRecord>(`/runs/${runId}/progress`);
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

export function getKSpaceNativeCatalog(runId: string): Promise<KSpaceNativeCatalogResponse> {
  return request<KSpaceNativeCatalogResponse>(`/runs/${runId}/kspace-native/catalog`);
}

export function getKSpaceNativeLesserSlice(
  runId: string,
  params: {
    row_start: number;
    row_stop: number;
    col_start: number;
    col_stop: number;
    k_start: number;
    k_stop: number;
    nambu_start: number;
    nambu_stop: number;
  },
): Promise<KSpaceNativeLesserSliceResponse> {
  const searchParams = new URLSearchParams(
    Object.entries(params).map(([key, value]) => [key, String(value)]),
  );
  return request<KSpaceNativeLesserSliceResponse>(`/runs/${runId}/kspace-native/lesser?${searchParams.toString()}`);
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

// --- Job Groups ---

export function listJobGroups(params: { study_id?: string } = {}): Promise<JobGroupRecord[]> {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null) as [string, string][],
  );
  return request<JobGroupRecord[]>(`/job-groups${q.size ? "?" + q.toString() : ""}`);
}

export function launchJobGroup(data: JobGroupLaunchRequest): Promise<JobGroupRecord> {
  return request<JobGroupRecord>("/job-groups/launch", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getJobGroup(groupId: string): Promise<JobGroupRecord> {
  return request<JobGroupRecord>(`/job-groups/${groupId}`);
}

// --- Sweeps ---

export function listSweeps(params: { study_id?: string } = {}): Promise<SweepRecord[]> {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null) as [string, string][],
  );
  return request<SweepRecord[]>(`/sweeps${q.size ? "?" + q.toString() : ""}`);
}

export function launchSweep(data: SweepLaunchRequest): Promise<SweepRecord> {
  return request<SweepRecord>("/sweeps/launch", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getSweep(sweepId: string): Promise<SweepRecord> {
  return request<SweepRecord>(`/sweeps/${sweepId}`);
}

// --- Derived Analyses ---

export function listDerivedAnalyses(params: {
  study_id?: string;
  source_kind?: DerivedAnalysisSourceKind;
  source_id?: string;
} = {}): Promise<DerivedAnalysisArtifactRecord[]> {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null) as [string, string][],
  );
  return request<DerivedAnalysisArtifactRecord[]>(`/derived-analyses${q.size ? "?" + q.toString() : ""}`);
}

export function launchDerivedAnalysis(data: DerivedAnalysisLaunchRequest): Promise<DerivedAnalysisArtifactRecord> {
  return request<DerivedAnalysisArtifactRecord>("/derived-analyses/launch", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getDerivedAnalysis(analysisId: string): Promise<DerivedAnalysisArtifactRecord> {
  return request<DerivedAnalysisArtifactRecord>(`/derived-analyses/${analysisId}`);
}

export function getDerivedAnalysisResult(analysisId: string): Promise<DerivedAnalysisResultRecord> {
  return request<DerivedAnalysisResultRecord>(`/derived-analyses/${analysisId}/result`);
}

// --- Evidence Bundles ---

export function createEvidenceBundle(data: {
  study_id: string;
  name: string;
  claim_candidate?: string;
  validation_scope?: string;
  artifact_refs?: { artifact_kind: string; artifact_id: string }[];
  analysis_ids?: string[];
  supports_bundle_ids?: string[];
  reproduction_recipe?: string;
  status?: EvidenceBundleStatus;
}): Promise<EvidenceBundleRecord> {
  return request<EvidenceBundleRecord>("/evidence-bundles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function patchEvidenceBundle(bundleId: string, patch: EvidenceBundlePatch): Promise<EvidenceBundleRecord> {
  return request<EvidenceBundleRecord>(`/evidence-bundles/${bundleId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function getEvidenceBundleResolved(bundleId: string): Promise<EvidenceBundleResolvedRecord> {
  return request<EvidenceBundleResolvedRecord>(`/evidence-bundles/${bundleId}/resolved`);
}
