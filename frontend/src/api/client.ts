import type {
  ObservableCatalogResponse,
  ObservableResponse,
  RunDetail,
  RunSummary,
  SimulationConfigInput,
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

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}`);
}

export function listObservables(runId: string): Promise<ObservableCatalogResponse> {
  return request<ObservableCatalogResponse>(`/runs/${runId}/observables`);
}

export function getObservable(runId: string, name: string): Promise<ObservableResponse> {
  return request<ObservableResponse>(`/runs/${runId}/observables/${name}`);
}
