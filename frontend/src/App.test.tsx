import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";
import { createDefaultConfig } from "./lib/defaultConfig";
import type { InteractionConfigInput, KbeConfigInput, ThermalBranchConfigInput } from "./lib/defaultConfig";
import { createFallbackPresets } from "./lib/workbench";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
    cleanup();
  });

  it("loads presets, launches a run, and shows the single-job workbench surfaces", async () => {
    vi.stubGlobal("fetch", createFetchMock() as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Preset Library");
    expect(screen.getByRole("button", { name: /Single Job/i })).toHaveAttribute("aria-current", "page");

    await user.click(screen.getByRole("button", { name: "Load Bond-d KBE-HFB scaffold" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Run Name")).toHaveValue("square-4x4-bond-d-kbe-hfb");
    });

    await user.click(screen.getByRole("button", { name: "Launch Run" }));

    await waitFor(() => {
      expect(screen.getAllByText("square-4x4-bond-d-kbe-hfb").length).toBeGreaterThan(0);
    });

    await screen.findByText("Observable Readout");
    await screen.findByText("Spectrum Preview");
    expect(screen.getByText("Baseline And Failure Context")).toBeInTheDocument();
    expect(screen.getByText("Notes, Analysis, And Bundles")).toBeInTheDocument();
  });

  it("switches to compare planning mode", async () => {
    vi.stubGlobal("fetch", createFetchMock() as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Research Surfaces");
    await user.click(screen.getByRole("button", { name: /Compare Jobs/i }));

    await screen.findByText("Read The Job Group Before The Plots");
    expect(screen.getByText("Variant Rail")).toBeInTheDocument();
    expect(screen.getByText("comparison_kind")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/compare-jobs");
    expect(screen.queryByText("Runs And Queue")).not.toBeInTheDocument();
  });

  it("stages and launches the Higgs demo from quick start", async () => {
    vi.stubGlobal("fetch", createFetchMock() as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Higgs Demo Quick Start");
    await user.click(screen.getByRole("button", { name: "Stage Demo" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Run Name")).toHaveValue("square-4x4-higgs-demo-kbe-hfb");
    });
    expect(screen.getByText(/Preset: square-4x4-higgs-demo-kbe-hfb/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Launch Demo" }));

    await waitFor(() => {
      expect(screen.getAllByText("square-4x4-higgs-demo-kbe-hfb").length).toBeGreaterThan(0);
    });
    await waitFor(() => {
      expect(screen.getAllByText(/Pairing D/i).length).toBeGreaterThan(0);
    });
  });

  it("loads a saved KBE run and exposes green-function slices", async () => {
    const kbeConfig = createDefaultConfig();
    const interactionDefaults = createDefaultConfig().interaction as InteractionConfigInput;
    const kbeDefaults = createDefaultConfig().kbe as KbeConfigInput;
    const thermalBranchDefaults = createDefaultConfig().thermal_branch as ThermalBranchConfigInput;
    kbeConfig.name = "kbe-reference";
    kbeConfig.solver = "kbe_hfb";
    kbeConfig.interaction = {
      ...((kbeConfig.interaction ?? interactionDefaults) as InteractionConfigInput),
      pairing_channel: "bond_d",
    };
    kbeConfig.kbe = {
      ...((kbeConfig.kbe ?? kbeDefaults) as KbeConfigInput),
      self_energy: "second_born_reference",
    };
    kbeConfig.thermal_branch = {
      ...((kbeConfig.thermal_branch ?? thermalBranchDefaults) as ThermalBranchConfigInput),
      enabled: true,
    };

    vi.stubGlobal(
      "fetch",
      createFetchMock({
        "run-kbe-001": kbeConfig,
      }) as unknown as typeof fetch,
    );

    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText("kbe-reference").length).toBeGreaterThan(0);
    });
    await screen.findByText("Green Function Slice");
    await waitFor(() => {
      expect(screen.getAllByText("Retarded").length).toBeGreaterThan(0);
    });
    await waitFor(() => {
      expect(screen.getAllByText("Slice Shape").length).toBeGreaterThan(0);
      expect(screen.getAllByText("1 x 1 x 2 x 2").length).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole("button", { name: "Thermal" }));
    await screen.findByText("Thermal Branch (Matsubara)");
    await user.click(screen.getByRole("button", { name: "Mixed" }));
    await screen.findByText("Mixed Green Function");
  });

  it("shows run log panel for completed runs", async () => {
    vi.stubGlobal("fetch", createFetchMock({
      "run-log-001": createDefaultConfig(),
    }) as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText("square-4x4-baseline").length).toBeGreaterThan(0);
    });

    const showLogButton = await screen.findByText("▸ Show log");
    await user.click(showLogButton);

    await screen.findByText(/solver started/);
  });
});

function createFetchMock(initialRuns: Record<string, ReturnType<typeof createDefaultConfig>> = {}) {
  const runConfigs = new Map<string, ReturnType<typeof createDefaultConfig>>(Object.entries(initialRuns));
  let runCount = Object.keys(initialRuns).length;
  const presets = createFallbackPresets();

  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost:8000");
    const method = init?.method ?? "GET";

    if (url.pathname === "/api/v1/presets" && method === "GET") {
      return Promise.resolve(jsonResponse(200, presets));
    }

    if (url.pathname === "/api/v1/runs" && method === "GET") {
      const payload = Array.from(runConfigs.entries())
        .map(([runId, config]) => buildRunSummary(runId, config))
        .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
      return Promise.resolve(jsonResponse(200, payload));
    }

    if (url.pathname === "/api/v1/runs" && method === "POST") {
      runCount += 1;
      const runId = `run-${String(runCount).padStart(3, "0")}`;
      const submittedConfig = JSON.parse(String(init?.body ?? "{}")) as ReturnType<typeof createDefaultConfig>;
      runConfigs.set(runId, submittedConfig);
      return Promise.resolve(jsonResponse(202, buildRunDetail(runId, submittedConfig)));
    }

    const runMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)$/);
    if (runMatch && method === "GET") {
      const runId = runMatch[1];
      const config = runConfigs.get(runId);
      if (!config) {
        return Promise.resolve(jsonResponse(404, { detail: "run not found" }));
      }
      return Promise.resolve(jsonResponse(200, buildRunDetail(runId, config)));
    }

    const observablesMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/observables$/);
    if (observablesMatch && method === "GET") {
      const runId = observablesMatch[1];
      const config = runConfigs.get(runId);
      if (!config) {
        return Promise.resolve(jsonResponse(404, { detail: "run not found" }));
      }
      return Promise.resolve(
        jsonResponse(200, {
          observables: buildAvailableObservables(config).map((item) => item.name),
        }),
      );
    }

    const observableMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/observables\/([^/]+)$/);
    if (observableMatch && method === "GET") {
      const [, runId, observable] = observableMatch;
      const config = runConfigs.get(runId);
      if (!config) {
        return Promise.resolve(jsonResponse(404, { detail: "run not found" }));
      }
      return Promise.resolve(jsonResponse(200, buildObservablePayload(runId, observable, config)));
    }

    const greenCatalogMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/green-functions$/);
    if (greenCatalogMatch && method === "GET") {
      const runId = greenCatalogMatch[1];
      const config = runConfigs.get(runId);
      if (!config) {
        return Promise.resolve(jsonResponse(404, { detail: "run not found" }));
      }
      if (config.solver !== "kbe_hfb") {
        return Promise.resolve(jsonResponse(404, { detail: "green function data not found" }));
      }
      return Promise.resolve(
        jsonResponse(200, {
          components: ["retarded", "lesser"],
          time_point_count: 3,
          shape: [3, 3, 2, 2],
          nambu_dimension: 2,
        }),
      );
    }

    const greenSliceMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/green-functions\/([^/]+)$/);
    if (greenSliceMatch && method === "GET") {
      const [, runId, component] = greenSliceMatch;
      const config = runConfigs.get(runId);
      if (!config) {
        return Promise.resolve(jsonResponse(404, { detail: "run not found" }));
      }
      if (config.solver !== "kbe_hfb") {
        return Promise.resolve(jsonResponse(404, { detail: "green function data not found" }));
      }
      return Promise.resolve(
        jsonResponse(200, {
          component,
          shape: [1, 1, 2, 2],
          times_row: [0],
          times_col: [0],
          real: [[[[1, 0], [0, 1]]]],
          imag: [[[[0, 0.2], [-0.2, 0]]]],
        }),
      );
    }

    const thermalCatalogMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/thermal-branch$/);
    if (thermalCatalogMatch && method === "GET") {
      const runId = thermalCatalogMatch[1];
      const config = runConfigs.get(runId);
      if (!config || config.solver !== "kbe_hfb") {
        return Promise.resolve(jsonResponse(404, { detail: "not found" }));
      }
      return Promise.resolve(
        jsonResponse(200, {
          components: ["matsubara"],
          tau_point_count: 5,
          shape: [5, 2, 2],
          nambu_dimension: 2,
        }),
      );
    }

    const thermalSliceMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/thermal-branch\/([^/]+)$/);
    if (thermalSliceMatch && method === "GET") {
      const [, , component] = thermalSliceMatch;
      return Promise.resolve(
        jsonResponse(200, {
          component,
          shape: [1, 2, 2],
          tau: [0],
          nambu_start: 0,
          nambu_stop: 2,
          real: [[[0.1, 0], [0, 0.1]]],
          imag: [[[0, 0.02], [-0.02, 0]]],
        }),
      );
    }

    const mixedCatalogMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/mixed-green-functions$/);
    if (mixedCatalogMatch && method === "GET") {
      const runId = mixedCatalogMatch[1];
      const config = runConfigs.get(runId);
      if (!config || config.solver !== "kbe_hfb") {
        return Promise.resolve(jsonResponse(404, { detail: "not found" }));
      }
      return Promise.resolve(
        jsonResponse(200, {
          components: ["mixed_lesser"],
          time_point_count: 3,
          tau_point_count: 5,
          shape: [3, 5, 2, 2],
          nambu_dimension: 2,
        }),
      );
    }

    const mixedSliceMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/mixed-green-functions\/([^/]+)$/);
    if (mixedSliceMatch && method === "GET") {
      const [, , component] = mixedSliceMatch;
      return Promise.resolve(
        jsonResponse(200, {
          component,
          shape: [1, 1, 2, 2],
          times: [0],
          tau: [0],
          nambu_start: 0,
          nambu_stop: 2,
          real: [[[[0.05, 0], [0, 0.05]]]],
          imag: [[[[0, 0.01], [-0.01, 0]]]],
        }),
      );
    }

    const logMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/log$/);
    if (logMatch && method === "GET") {
      return Promise.resolve(textResponse(200, "solver started\nstep 1 ok\nfinished"));
    }

    throw new Error(`unexpected fetch ${method} ${url.pathname}`);
  });
}

function buildRunSummary(runId: string, config: ReturnType<typeof createDefaultConfig>) {
  return {
    run_id: runId,
    name: config.name,
    solver: config.solver,
    state: "succeeded",
    created_at: "2026-03-17T00:00:00Z",
    updated_at: "2026-03-17T00:00:00Z",
    status_message: "completed",
  };
}

function buildRunDetail(runId: string, config: ReturnType<typeof createDefaultConfig>) {
  return {
    run_id: runId,
    name: config.name,
    solver: config.solver,
    state: "succeeded",
    created_at: "2026-03-17T00:00:00Z",
    updated_at: "2026-03-17T00:00:00Z",
    started_at: "2026-03-17T00:00:00Z",
    finished_at: "2026-03-17T00:00:01Z",
    status_message: "completed",
    lattice: {
      nx: config.lattice.nx,
      ny: config.lattice.ny,
    },
    time_grid: {
      dt: config.time.dt,
      t_final: config.time.t_final,
    },
    available_observables: buildAvailableObservables(config),
    diagnostics_excerpt: {
      site_count: config.lattice.nx * config.lattice.ny,
    },
    diagnostics: {
      site_count: config.lattice.nx * config.lattice.ny,
      dt: config.time.dt,
      solver: config.solver,
    },
    config,
  };
}

function buildAvailableObservables(config: ReturnType<typeof createDefaultConfig>) {
  return (config.observables ?? ["density", "energy"]).map((name) => ({
    name,
    time_key: "time",
    series: [{ label: getSeriesLabel(name), key: getSeriesLabel(name) }],
    units: null,
    metadata: { solver: config.solver },
  }));
}

function buildObservablePayload(
  runId: string,
  observable: string,
  config: ReturnType<typeof createDefaultConfig>,
) {
  return {
    name: observable,
    time: [0, config.time.dt, config.time.dt * 2],
    series: [
      {
        label: getSeriesLabel(observable),
        values: buildObservableSeries(observable, runId),
      },
    ],
    units: null,
    metadata: { solver: config.solver },
  };
}

function getSeriesLabel(observable: string): string {
  if (observable === "energy") {
    return "total";
  }
  if (observable === "density") {
    return "mean";
  }
  if (observable.startsWith("pairing")) {
    return "magnitude";
  }
  return "value";
}

function buildObservableSeries(observable: string, runId: string): number[] {
  const offset = runOffset(runId);

  if (observable === "energy") {
    return [-2.0, -1.9 + offset, -1.8 + offset];
  }

  if (observable.startsWith("pairing")) {
    return [0.2, 0.2 + offset, 0.18 + offset * 2];
  }

  if (observable === "vector_potential") {
    return [0.0, 0.05 + offset, 0.02 + offset * 2];
  }

  return [0.5, 0.5 + offset, 0.5 + offset * 2];
}

function runOffset(runId: string): number {
  return runId.endsWith("1") ? 0.02 : 0.05;
}

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

function textResponse(status: number, body: string): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 400 ? "error" : "ok",
    headers: {
      get(name: string) {
        return name.toLowerCase() === "content-type" ? "text/plain" : null;
      },
    },
    text: async () => body,
  } as Response;
}
