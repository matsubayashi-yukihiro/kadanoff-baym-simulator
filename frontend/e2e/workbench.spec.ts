import { expect, test, type Page, type Route } from "@playwright/test";

const API_ORIGIN = "http://localhost:8000";
const API_PREFIX = `${API_ORIGIN}/api/v1`;

type ScenarioName =
  | "single-job-cancel"
  | "single-job-kspace"
  | "compare-jobs-url"
  | "parameter-sweep-url";

type MockRun = {
  detail: Record<string, unknown>;
  detailSequence?: Record<string, unknown>[];
  progressSequence?: Record<string, unknown>[];
  observableCatalog?: Record<string, unknown>;
  observableData?: Record<string, Record<string, unknown>>;
  log?: string;
  detailReads: number;
  progressReads: number;
};

type MockAnalysis = {
  record: Record<string, unknown>;
  result: Record<string, unknown>;
};

type MockState = {
  runs: Record<string, MockRun>;
  groups: Record<string, Record<string, unknown>>;
  sweeps: Record<string, Record<string, unknown>>;
  analyses: Record<string, MockAnalysis>;
  nextCreatedRun: MockRun | null;
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
});

test("Single Job launch, progress, and cancel workflow", async ({ page }) => {
  await installWorkbenchApiMock(page, "single-job-cancel");

  await page.goto("/");
  await page.getByRole("button", { name: "Launch Run" }).click();

  await expect(page.getByRole("heading", { name: "Live Run Progress" })).toBeVisible();
  await expect(page.getByText("solver warmup")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel Run" })).toBeVisible();

  await page.getByRole("button", { name: "Cancel Run" }).click();

  await expect(page.locator(".status-pill").filter({ hasText: "cancelled" }).first()).toBeVisible();
  await expect(page.locator(".sjp-run-status-msg")).toHaveText("run cancelled");
});

test("Single Job restores a k-space run and auto-launches derived analyses", async ({ page }) => {
  await installWorkbenchApiMock(page, "single-job-kspace");

  await page.goto("/?run=run-kspace-001");

  const spectralPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "K-Path Spectral Function" }),
  });
  const trArpesPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "tr-ARPES Intensity" }),
  });

  await expect(spectralPanel.getByRole("button", { name: "Recompute" })).toBeVisible();
  await expect(spectralPanel.locator(".js-plotly-plot")).toBeVisible();
  await expect(trArpesPanel.getByRole("button", { name: "Recompute" })).toBeVisible();
  await expect(trArpesPanel.locator(".js-plotly-plot")).toBeVisible();
});

test("Compare Jobs restores selected group from URL and shows k-space compare result", async ({ page }) => {
  await installWorkbenchApiMock(page, "compare-jobs-url");

  await page.goto("/compare-jobs?group=group-e2e-001");

  const comparePanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "K-Path Spectral Compare" }),
  });

  await expect(page.getByRole("heading", { name: "compare-group-e2e" })).toBeVisible();
  await expect(comparePanel.getByRole("button", { name: "Recompute" })).toBeVisible();
  await expect(comparePanel.locator(".js-plotly-plot")).toBeVisible();
});

test("Parameter Sweep restores selected sweep from URL and shows tr-ARPES heatmap", async ({ page }) => {
  await installWorkbenchApiMock(page, "parameter-sweep-url");

  await page.goto("/parameter-sweep?sweep=sweep-e2e-001");

  const heatmapPanel = page.locator("section.panel").filter({
    has: page.getByRole("heading", { name: "tr-ARPES Sweep Heatmap" }),
  });

  await expect(page.getByRole("heading", { name: "sweep-e2e" })).toBeVisible();
  await expect(heatmapPanel.getByRole("button", { name: "Recompute" })).toBeVisible();
  await expect(heatmapPanel.locator(".js-plotly-plot")).toBeVisible();
});

async function installWorkbenchApiMock(page: Page, scenario: ScenarioName) {
  const state = createScenarioState(scenario);
  await page.route(`${API_ORIGIN}/**`, async (route) => {
    await handleApiRoute(route, state);
  });
}

async function handleApiRoute(route: Route, state: MockState) {
  const request = route.request();
  const url = new URL(request.url());
  const method = request.method();

  if (url.pathname === "/openapi.json") {
    await fulfillJson(route, {
      paths: {
        "/api/v1/derived-analyses/launch": {},
      },
      components: {
        schemas: {
          "SimulationConfig-Input": {
            properties: {
              equilibrium: {},
              representation: {},
            },
          },
        },
      },
    });
    return;
  }

  if (!url.pathname.startsWith("/api/v1/")) {
    await fulfillJson(route, { detail: `unhandled mock path: ${method} ${url.pathname}` }, 404);
    return;
  }

  if (url.pathname === "/api/v1/presets" && method === "GET") {
    await fulfillJson(route, []);
    return;
  }

  if (url.pathname === "/api/v1/studies" && method === "GET") {
    await fulfillJson(route, []);
    return;
  }

  if (url.pathname === "/api/v1/decision-notes" && method === "GET") {
    await fulfillJson(route, []);
    return;
  }

  if (url.pathname === "/api/v1/evidence-bundles" && method === "GET") {
    await fulfillJson(route, []);
    return;
  }

  if (url.pathname === "/api/v1/runs" && method === "GET") {
    await fulfillJson(route, Object.values(state.runs).map((run) => toRunSummary(run.detail)));
    return;
  }

  if (url.pathname === "/api/v1/runs" && method === "POST") {
    if (state.nextCreatedRun == null) {
      await fulfillJson(route, { detail: "no mocked run available" }, 500);
      return;
    }
    const run = clone(state.nextCreatedRun);
    const runId = String(run.detail.run_id);
    state.runs[runId] = run;
    state.nextCreatedRun = null;
    await fulfillJson(route, run.detail, 202);
    return;
  }

  const runProgressMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/progress$/);
  if (runProgressMatch && method === "GET") {
    const run = state.runs[runProgressMatch[1]];
    if (!run) {
      await fulfillJson(route, { detail: "run not found" }, 404);
      return;
    }
    const payload = readSequencedRecord(run.progressSequence, "progressReads", run);
    await fulfillJson(route, payload ?? makeProgressRecord({ runId: runProgressMatch[1], state: "running", phase: "propagating" }));
    return;
  }

  const runCancelMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/cancel$/);
  if (runCancelMatch && method === "POST") {
    const run = state.runs[runCancelMatch[1]];
    if (!run) {
      await fulfillJson(route, { detail: "run not found" }, 404);
      return;
    }
    run.detail = {
      ...run.detail,
      state: "cancelled",
      updated_at: isoTime(20),
      finished_at: isoTime(20),
      status_message: "run cancelled",
    };
    run.detailSequence = [clone(run.detail)];
    run.progressSequence = [
      makeProgressRecord({
        runId: String(run.detail.run_id),
        state: "cancelled",
        phase: "cancelled",
        statusLine: "run cancelled",
      }),
    ];
    await fulfillJson(route, run.detail);
    return;
  }

  const runLogMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/log$/);
  if (runLogMatch && method === "GET") {
    const run = state.runs[runLogMatch[1]];
    await route.fulfill({
      status: run ? 200 : 404,
      contentType: "text/plain",
      body: run?.log ?? "",
    });
    return;
  }

  const observableMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/observables\/([^/]+)$/);
  if (observableMatch && method === "GET") {
    const run = state.runs[observableMatch[1]];
    const payload = run?.observableData?.[observableMatch[2]];
    await fulfillJson(route, payload ?? { detail: "observable not found" }, payload ? 200 : 404);
    return;
  }

  const observableCatalogMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/observables$/);
  if (observableCatalogMatch && method === "GET") {
    const run = state.runs[observableCatalogMatch[1]];
    await fulfillJson(route, run?.observableCatalog ?? { run_id: observableCatalogMatch[1], observables: [] });
    return;
  }

  const kspaceCatalogMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/kspace-native\/catalog$/);
  if (kspaceCatalogMatch && method === "GET") {
    await fulfillJson(route, {
      run_id: kspaceCatalogMatch[1],
      components: ["lesser"],
      time_point_count: 2,
      k_point_count: 1,
      nambu_dimension: 2,
      reconstruction_mode: "k_space_native_trajectory",
      points: [
        {
          index: 0,
          grid_index_x: 0,
          grid_index_y: 0,
          kx: 0,
          ky: 0,
        },
      ],
    });
    return;
  }

  const kspaceSliceMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/kspace-native\/lesser$/);
  if (kspaceSliceMatch && method === "GET") {
    await fulfillJson(route, {
      run_id: kspaceSliceMatch[1],
      component: "lesser",
      times_row: [0],
      times_col: [0],
      shape: [1, 1, 1, 2, 2],
      real: [[[[[0.1, 0.0], [0.0, 0.1]]]]],
      imag: [[[[[0.0, -0.05], [0.05, 0.0]]]]],
    });
    return;
  }

  const runMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)$/);
  if (runMatch && method === "GET") {
    const run = state.runs[runMatch[1]];
    if (!run) {
      await fulfillJson(route, { detail: "run not found" }, 404);
      return;
    }
    const payload = readSequencedRecord(run.detailSequence, "detailReads", run) ?? run.detail;
    run.detail = clone(payload);
    await fulfillJson(route, payload);
    return;
  }

  if (url.pathname === "/api/v1/job-groups" && method === "GET") {
    await fulfillJson(route, Object.values(state.groups));
    return;
  }

  const groupMatch = url.pathname.match(/^\/api\/v1\/job-groups\/([^/]+)$/);
  if (groupMatch && method === "GET") {
    const group = state.groups[groupMatch[1]];
    await fulfillJson(route, group ?? { detail: "group not found" }, group ? 200 : 404);
    return;
  }

  if (url.pathname === "/api/v1/sweeps" && method === "GET") {
    await fulfillJson(route, Object.values(state.sweeps));
    return;
  }

  const sweepMatch = url.pathname.match(/^\/api\/v1\/sweeps\/([^/]+)$/);
  if (sweepMatch && method === "GET") {
    const sweep = state.sweeps[sweepMatch[1]];
    await fulfillJson(route, sweep ?? { detail: "sweep not found" }, sweep ? 200 : 404);
    return;
  }

  if (url.pathname === "/api/v1/derived-analyses" && method === "GET") {
    const sourceKind = url.searchParams.get("source_kind");
    const sourceId = url.searchParams.get("source_id");
    const filtered = Object.values(state.analyses)
      .map((entry) => entry.record)
      .filter((record) => {
        if (sourceKind && record.source_kind !== sourceKind) return false;
        if (sourceId && record.source_id !== sourceId) return false;
        return true;
      });
    await fulfillJson(route, filtered);
    return;
  }

  if (url.pathname === "/api/v1/derived-analyses/launch" && method === "POST") {
    const payload = request.postDataJSON() as {
      source_kind: string;
      source_id: string;
      analysis_type: string;
    };
    const analysis = createAnalysis(payload.source_kind, payload.source_id, payload.analysis_type);
    state.analyses[analysis.record.analysis_id as string] = analysis;
    await fulfillJson(route, analysis.record, 201);
    return;
  }

  const analysisResultMatch = url.pathname.match(/^\/api\/v1\/derived-analyses\/([^/]+)\/result$/);
  if (analysisResultMatch && method === "GET") {
    const analysis = state.analyses[analysisResultMatch[1]];
    await fulfillJson(route, analysis?.result ?? { detail: "analysis result not found" }, analysis ? 200 : 404);
    return;
  }

  const analysisMatch = url.pathname.match(/^\/api\/v1\/derived-analyses\/([^/]+)$/);
  if (analysisMatch && method === "GET") {
    const analysis = state.analyses[analysisMatch[1]];
    await fulfillJson(route, analysis?.record ?? { detail: "analysis not found" }, analysis ? 200 : 404);
    return;
  }

  await fulfillJson(route, { detail: `unhandled mock path: ${method} ${url.pathname}` }, 404);
}

function createScenarioState(scenario: ScenarioName): MockState {
  switch (scenario) {
    case "single-job-cancel": {
      return {
        runs: {},
        groups: {},
        sweeps: {},
        analyses: {},
        nextCreatedRun: {
          detail: makeRunDetail({
            runId: "run-cancel-001",
            name: "cancel-e2e-run",
            state: "running",
            solver: "noninteracting",
            representation: "real_space",
            statusMessage: "solver running",
          }),
          detailSequence: [makeRunDetail({
            runId: "run-cancel-001",
            name: "cancel-e2e-run",
            state: "running",
            solver: "noninteracting",
            representation: "real_space",
            statusMessage: "solver running",
          })],
          progressSequence: [
            makeProgressRecord({
              runId: "run-cancel-001",
              state: "running",
              phase: "equilibrium",
              physicalProgressFraction: 0.25,
              statusLine: "solver warmup",
            }),
            makeProgressRecord({
              runId: "run-cancel-001",
              state: "running",
              phase: "propagating",
              physicalProgressFraction: 0.55,
              statusLine: "solver warmup",
            }),
          ],
          log: "",
          detailReads: 0,
          progressReads: 0,
        },
      };
    }
    case "single-job-kspace": {
      const run = createMockRun({
        detail: makeRunDetail({
          runId: "run-kspace-001",
          name: "kspace-e2e-run",
          state: "succeeded",
          solver: "kbe_hfb",
          representation: "k_space",
          statusMessage: "simulation completed",
        }),
        observableCatalog: {
          run_id: "run-kspace-001",
          observables: ["density"],
        },
        observableData: {
          density: {
            run_id: "run-kspace-001",
            name: "density",
            time: [0, 0.2, 0.4],
            series: [{ label: "mean", values: [0.5, 0.49, 0.48] }],
          },
        },
      });
      return {
        runs: { "run-kspace-001": run },
        groups: {},
        sweeps: {},
        analyses: {},
        nextCreatedRun: null,
      };
    }
    case "compare-jobs-url": {
      const childRun = createMockRun({
        detail: makeRunDetail({
          runId: "run-group-child-001",
          name: "group-child-run",
          state: "succeeded_with_warnings",
          solver: "kbe_hfb",
          representation: "k_space",
          statusMessage: "completed with warnings",
        }),
      });
      return {
        runs: { "run-group-child-001": childRun },
        groups: {
          "group-e2e-001": {
            group_id: "group-e2e-001",
            name: "compare-group-e2e",
            state: "succeeded",
            comparison_kind: "physics_hypothesis",
            child_run_ids: ["run-group-child-001"],
            variants: [
              {
                label: "variant-A",
                description: "k-space reference variant",
                run_id: "run-group-child-001",
              },
            ],
          },
        },
        sweeps: {},
        analyses: {},
        nextCreatedRun: null,
      };
    }
    case "parameter-sweep-url": {
      const childRun = createMockRun({
        detail: makeRunDetail({
          runId: "run-sweep-child-001",
          name: "sweep-child-run",
          state: "succeeded",
          solver: "tdhfb",
          representation: "k_space",
          statusMessage: "simulation completed",
        }),
      });
      return {
        runs: { "run-sweep-child-001": childRun },
        groups: {},
        sweeps: {
          "sweep-e2e-001": {
            sweep_id: "sweep-e2e-001",
            name: "sweep-e2e",
            state: "succeeded",
            parameter_label: "drive.amplitude_x",
            child_run_ids: ["run-sweep-child-001"],
            values: [0.1],
          },
        },
        analyses: {},
        nextCreatedRun: null,
      };
    }
  }
}

function createMockRun(init: Omit<MockRun, "detailReads" | "progressReads">): MockRun {
  return {
    ...init,
    detailReads: 0,
    progressReads: 0,
  };
}

function makeRunDetail(args: {
  runId: string;
  name: string;
  state: string;
  solver: string;
  representation: "real_space" | "k_space";
  statusMessage: string;
}) {
  return {
    run_id: args.runId,
    name: args.name,
    solver: args.solver,
    state: args.state,
    created_at: isoTime(0),
    updated_at: isoTime(10),
    started_at: isoTime(2),
    finished_at: args.state === "queued" || args.state === "running" ? null : isoTime(12),
    status_message: args.statusMessage,
    lattice: {
      nx: 2,
      ny: 2,
      boundary: "periodic",
      hopping: 1.0,
      chemical_potential: 0.0,
    },
    time_grid: {
      dt: 0.1,
      t_final: 0.4,
    },
    available_observables: ["density"],
    diagnostics_excerpt: {},
    diagnostics: {},
    research_metadata: {
      study_id: null,
      run_role: null,
      validation_status: "unchecked",
    },
    config: {
      name: args.name,
      solver: args.solver,
      representation: args.representation,
      lattice: {
        kind: "square",
        nx: 2,
        ny: 2,
        boundary: "periodic",
        hopping: 1.0,
        chemical_potential: 0.0,
      },
      time: {
        t_final: 0.4,
        dt: 0.1,
        save_every: 1,
      },
      drive: {
        drive_type: "gaussian",
        amplitude_x: 0.25,
        amplitude_y: 0.0,
        frequency: 2.0,
        phase: 0.0,
        center: 0.2,
        width: 0.15,
      },
      interaction: {
        onsite_u: args.solver === "noninteracting" ? 0.0 : -1.2,
        nearest_neighbor_v: 0.0,
        pairing_channel: "none",
      },
      initial_state: {
        filling: 0.5,
        temperature: 0.2,
        seed_pairing: 0.0,
      },
      equilibrium: {
        method: "hfb",
        allow_approximation_mismatch: true,
      },
      kbe: {
        self_energy: args.solver === "kbe_hfb" ? "second_born_reference" : "hfb",
        max_fixed_point_iterations: 8,
        tolerance: 1e-6,
        mixing: 0.5,
      },
      adaptive: {
        enabled: false,
      },
      thermal_branch: {
        enabled: args.solver === "kbe_hfb",
        n_tau: 8,
        max_iterations: 10,
        mixing: 0.4,
      },
      observables: ["density"],
    },
  };
}

function toRunSummary(detail: Record<string, unknown>) {
  return {
    run_id: detail.run_id,
    name: detail.name,
    solver: detail.solver,
    state: detail.state,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
    lattice: detail.lattice,
    research_metadata: detail.research_metadata,
  };
}

function makeProgressRecord(args: {
  runId: string;
  state: string;
  phase: string;
  physicalProgressFraction?: number;
  statusLine?: string;
}) {
  const fraction = args.physicalProgressFraction ?? 0.5;
  return {
    run_id: args.runId,
    state: args.state,
    phase: args.phase,
    updated_at: isoTime(8),
    wall_seconds_elapsed: 1.5,
    physical_time_current: Number((0.4 * fraction).toFixed(3)),
    physical_time_final: 0.4,
    physical_progress_fraction: fraction,
    accepted_steps: Math.max(1, Math.round(fraction * 4)),
    requested_steps: 4,
    rejected_steps: 0,
    saved_samples_written: Math.max(1, Math.round(fraction * 3)),
    status_line: args.statusLine ?? null,
    solver_metrics: {
      current_time_index: Math.max(1, Math.round(fraction * 4)),
    },
    history: [
      {
        wall_seconds_elapsed: 0.5,
        physical_progress_fraction: Math.max(0.1, fraction / 2),
        saved_samples_written: 1,
      },
      {
        wall_seconds_elapsed: 1.5,
        physical_progress_fraction: fraction,
        saved_samples_written: Math.max(1, Math.round(fraction * 3)),
      },
    ],
  };
}

function createAnalysis(sourceKind: string, sourceId: string, analysisType: string): MockAnalysis {
  const analysisId = `${sourceKind}-${sourceId}-${analysisType}`;
  return {
    record: {
      analysis_id: analysisId,
      study_id: "__none__",
      source_kind: sourceKind,
      source_id: sourceId,
      analysis_type: analysisType,
      analysis_version: "v1",
      status: "succeeded",
      created_at: isoTime(0),
      updated_at: isoTime(5),
    },
    result: {
      analysis_id: analysisId,
      payload: makeAnalysisPayload(sourceKind, analysisType),
      created_at: isoTime(5),
    },
  };
}

function makeAnalysisPayload(sourceKind: string, analysisType: string) {
  if (sourceKind === "run" && analysisType === "k_spectral_preview") {
    return {
      intensity: [
        [0.2, 0.4, 0.3],
        [0.3, 0.6, 0.4],
        [0.2, 0.5, 0.3],
      ],
      energy: [-1, 0, 1],
      k_surface: {
        tick_positions: [0, 1, 2],
        tick_labels: ["Γ", "X", "M"],
      },
    };
  }
  if (sourceKind === "run" && analysisType === "tr_arpes_preview") {
    return {
      intensity: [
        [0.1, 0.3, 0.2],
        [0.2, 0.5, 0.3],
      ],
      omega: [-0.5, 0, 0.5],
      probe_centers: [0.1, 0.3],
      probe_center_used: 0.1,
    };
  }
  if (sourceKind === "job_group" && analysisType === "k_spectral_compare") {
    return {
      variants: [
        {
          label: "variant-A",
          k_labels: ["Γ", "X", "M"],
          k_indices: [0, 1, 2],
          omega: [-1, 0, 1],
          spectrum: [
            [0.2, 0.4, 0.3],
            [0.3, 0.6, 0.4],
            [0.2, 0.5, 0.3],
          ],
        },
      ],
    };
  }
  if (sourceKind === "sweep" && analysisType === "tr_arpes_heatmap") {
    return {
      intensity: [[0.2, 0.5, 0.3]],
      energy: [-0.5, 0, 0.5],
      parameter_values: [0.1],
    };
  }
  return {};
}

function readSequencedRecord(
  sequence: Record<string, unknown>[] | undefined,
  counterKey: "detailReads" | "progressReads",
  run: MockRun,
) {
  if (!sequence || sequence.length === 0) {
    return null;
  }
  const index = Math.min(run[counterKey], sequence.length - 1);
  run[counterKey] += 1;
  return clone(sequence[index]);
}

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

function isoTime(seconds: number) {
  return new Date(Date.UTC(2026, 2, 25, 0, 0, seconds)).toISOString();
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
