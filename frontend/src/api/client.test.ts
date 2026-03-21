import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createDecisionNote,
  createRun,
  createStudy,
  getGreenFunctionSlice,
  getObservable,
  listDecisionNotes,
  listEvidenceBundles,
  listGreenFunctions,
  listRuns,
  listStudies,
  patchRunMetadata,
} from "./client";
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
      if (url.endsWith("/api/v1/runs/run-001/green-functions")) {
        return Promise.resolve(
          jsonResponse(200, {
            run_id: "run-001",
            components: ["retarded", "lesser"],
            shape: [3, 3, 8, 8],
            time_point_count: 3,
            nambu_dimension: 8,
          }),
        );
      }
      if (
        url.endsWith(
          "/api/v1/runs/run-001/green-functions/retarded?row_start=1&row_stop=2&col_start=1&col_stop=2&nambu_start=0&nambu_stop=2",
        )
      ) {
        return Promise.resolve(
          jsonResponse(200, {
            component: "retarded",
            times_row: [0.1],
            times_col: [0.1],
            nambu_start: 0,
            nambu_stop: 2,
            shape: [1, 1, 2, 2],
            real: [[[[0, 0], [0, 0]]]],
            imag: [[[[-1, 0], [0, -1]]]],
          }),
        );
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const runs = await listRuns();
    const run = await createRun(createDefaultConfig());
    const observable = await getObservable("run-001", "energy");
    const greenCatalog = await listGreenFunctions("run-001");
    const greenSlice = await getGreenFunctionSlice("run-001", "retarded", {
      row_start: 1,
      row_stop: 2,
      col_start: 1,
      col_stop: 2,
      nambu_start: 0,
      nambu_stop: 2,
    });

    expect(runs).toEqual([]);
    expect(run.run_id).toBe("run-001");
    expect(observable.name).toBe("energy");
    expect(greenCatalog.components).toEqual(["retarded", "lesser"]);
    expect(greenSlice.component).toBe("retarded");
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
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/api/v1/runs/run-001/green-functions",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://localhost:8000/api/v1/runs/run-001/green-functions/retarded?row_start=1&row_stop=2&col_start=1&col_stop=2&nambu_start=0&nambu_stop=2",
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

  it("includes validation locations and rejected extra inputs in ApiError messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(422, {
            detail: [
              { loc: ["body", "category"], msg: "Extra inputs are not permitted", input: "demo" },
              { loc: ["body", "validation_status"], msg: "Extra inputs are not permitted", input: "prototype" },
            ],
          }),
        ),
      ) as unknown as typeof fetch,
    );

    await expect(createRun(createDefaultConfig())).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: "ApiError",
        status: 422,
        message:
          'category: Extra inputs are not permitted (input="demo")\nvalidation_status: Extra inputs are not permitted (input="prototype")',
      }),
    );
  });

  it("retries createRun without legacy-unsupported default fields", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/runs") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        if ("representation" in body || "drive_type" in (body.drive ?? {})) {
          return Promise.resolve(
            jsonResponse(422, {
              detail: [
                { loc: ["body", "drive", "drive_type"], msg: "Extra inputs are not permitted", input: "gaussian" },
                { loc: ["body", "representation"], msg: "Extra inputs are not permitted", input: "real_space" },
              ],
            }),
          );
        }
        return Promise.resolve(
          jsonResponse(202, {
            run_id: "run-compat",
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
      throw new Error(`unexpected fetch ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const run = await createRun(createDefaultConfig());

    expect(run.run_id).toBe("run-compat");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const retriedBody = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    expect(retriedBody.representation).toBeUndefined();
    expect(retriedBody.drive.drive_type).toBeUndefined();
  });
});

const STUDY_FIXTURE = {
  study_id: "study-001",
  title: "Higgs test",
  question: "Does pairing_d respond?",
  status: "active",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
};

const NOTE_FIXTURE = {
  note_id: "note-001",
  study_id: "study-001",
  source_kind: "run",
  source_id: "run-001",
  note_kind: "observation",
  body: "pairing_d oscillates",
  created_at: "2026-03-01T00:00:00Z",
};

const BUNDLE_FIXTURE = {
  bundle_id: "bundle-001",
  study_id: "study-001",
  title: "Higgs evidence",
  claim_candidate: "pairing_d shows Higgs mode",
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
};

describe("research artifact client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("listStudies calls GET /api/v1/studies", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [STUDY_FIXTURE])));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    const result = await listStudies();
    expect(result).toEqual([STUDY_FIXTURE]);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/studies", expect.any(Object));
  });

  it("createStudy calls POST /api/v1/studies with body", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, STUDY_FIXTURE)));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    const result = await createStudy({ title: "Higgs test", question: "Does pairing_d respond?", status: "active" });
    expect(result.study_id).toBe("study-001");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/studies",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listDecisionNotes with source filters builds correct query string", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [NOTE_FIXTURE])));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    const result = await listDecisionNotes({ source_kind: "run", source_id: "run-001" });
    expect(result).toEqual([NOTE_FIXTURE]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/decision-notes?source_kind=run&source_id=run-001",
      expect.any(Object),
    );
  });

  it("listDecisionNotes with no params omits query string", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [])));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    await listDecisionNotes({});
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/decision-notes",
      expect.any(Object),
    );
  });

  it("createDecisionNote calls POST /api/v1/decision-notes", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(201, NOTE_FIXTURE)));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    const result = await createDecisionNote({
      study_id: "study-001",
      source_kind: "run",
      source_id: "run-001",
      note_kind: "observation",
      body: "pairing_d oscillates",
    });
    expect(result.note_id).toBe("note-001");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/decision-notes",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listEvidenceBundles with study_id builds correct query string", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, [BUNDLE_FIXTURE])));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    const result = await listEvidenceBundles({ study_id: "study-001" });
    expect(result).toEqual([BUNDLE_FIXTURE]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/evidence-bundles?study_id=study-001",
      expect.any(Object),
    );
  });

  it("patchRunMetadata calls PATCH /api/v1/runs/{run_id}/metadata", async () => {
    const runFixture = {
      run_id: "run-001",
      name: "baseline",
      solver: "noninteracting",
      state: "succeeded",
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
      started_at: null,
      finished_at: null,
      status_message: null,
      lattice: { nx: 4, ny: 4 },
      time_grid: { dt: 0.1, t_final: 1.0 },
      available_observables: [],
      diagnostics_excerpt: {},
      config: createDefaultConfig(),
      diagnostics: {},
      research_metadata: { study_id: "study-001" },
    };
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(200, runFixture)));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    const result = await patchRunMetadata("run-001", { study_id: "study-001" });
    expect(result.run_id).toBe("run-001");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/runs/run-001/metadata",
      expect.objectContaining({ method: "PATCH" }),
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
