import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createRun, getObservable, listRuns } from "./client";
import { createDefaultConfig } from "../lib/defaultConfig";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("uses the backend API base path for run and observable requests", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/runs") && (!init?.method || init.method === "GET")) {
        return Promise.resolve(jsonResponse(200, []));
      }
      if (url.endsWith("/api/v1/runs") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(202, {
            run_id: "run-001",
            name: "baseline",
            solver: "noninteracting",
            state: "queued",
            created_at: "2026-03-15T00:00:00Z",
            updated_at: "2026-03-15T00:00:00Z",
            started_at: null,
            finished_at: null,
            status_message: "run queued",
            lattice: { nx: 4, ny: 4 },
            time_grid: { dt: 0.1, t_final: 1.0 },
            available_observables: [],
            diagnostics_excerpt: {},
            config: createDefaultConfig(),
            diagnostics: {},
          }),
        );
      }
      if (url.endsWith("/api/v1/runs/run-001/observables/energy")) {
        return Promise.resolve(
          jsonResponse(200, {
            name: "energy",
            time: [0, 0.1],
            series: [{ label: "total", values: [-1.2, -1.18] }],
            units: null,
            metadata: { solver: "noninteracting" },
          }),
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const runs = await listRuns();
    const run = await createRun(createDefaultConfig());
    const observable = await getObservable("run-001", "energy");

    expect(runs).toEqual([]);
    expect(run.run_id).toBe("run-001");
    expect(observable.name).toBe("energy");
    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://localhost:8000/api/v1/runs", expect.any(Object));
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/runs",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/v1/runs/run-001/observables/energy",
      expect.any(Object),
    );
  });

  it("turns backend validation payloads into ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(422, {
            detail: [{ msg: "t_final must be an integer multiple of dt" }],
          }),
        ),
      ) as unknown as typeof fetch,
    );

    await expect(createRun(createDefaultConfig())).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: "ApiError",
        status: 422,
        message: "t_final must be an integer multiple of dt",
      }),
    );
  });
});

function jsonResponse(status: number, payload: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? "error" : "ok",
    headers: {
      get(name: string) {
        return name.toLowerCase() === "content-type" ? "application/json" : null;
      },
    },
    json: async () => payload,
  } as Response;
}
