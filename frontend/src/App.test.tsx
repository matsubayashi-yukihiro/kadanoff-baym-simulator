import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";
import { createDefaultConfig } from "./lib/defaultConfig";

describe("App workspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.localStorage.clear();
    cleanup();
  });

  it("duplicates jobs, edits the compact editor, switches tabs, and overlays successful runs", async () => {
    const fetchMock = createWorkspaceFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Editable DataFrame");

    await user.click(screen.getByRole("button", { name: /square-4x4-baseline duplicate/i }));
    await user.click(screen.getByRole("button", { name: /Core/i }));

    const rows = screen.getAllByTestId(/job-row-/);
    expect(rows).toHaveLength(2);

    const secondDtInput = screen.getByLabelText(/square-4x4-baseline copy Time Dt/i);
    await user.clear(secondDtInput);
    await user.type(secondDtInput, "0.2");
    await user.tab();
    expect(secondDtInput).toHaveValue("0.2");

    await user.click(screen.getByRole("button", { name: "Register Run" }));
    await waitFor(() => {
      expect(screen.getAllByText("run-001").length).toBeGreaterThan(0);
    });

    await user.click(screen.getAllByRole("tab")[0]);
    await user.click(screen.getByRole("button", { name: "Register Run" }));
    await waitFor(() => {
      expect(screen.getAllByText("run-002").length).toBeGreaterThan(0);
    });

    await screen.findByRole("img", { name: "compare-chart-1-density" });
    await waitFor(() => {
      expect(screen.getAllByText("square-4x4-baseline").length).toBeGreaterThan(0);
      expect(screen.getAllByText("square-4x4-baseline copy").length).toBeGreaterThan(0);
    });
  });

  it("renames and deletes duplicated jobs from the workspace", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("unexpected fetch"))) as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("Editable DataFrame");
    await user.click(screen.getByRole("button", { name: /square-4x4-baseline duplicate/i }));

    let rows = screen.getAllByTestId(/job-row-/);
    expect(rows).toHaveLength(2);

    const secondTitleInput = screen.getByLabelText(/square-4x4-baseline copy Job Name/i);
    await user.clear(secondTitleInput);
    await user.type(secondTitleInput, "pulseA");
    await user.tab();

    expect(secondTitleInput).toHaveValue("pulseA");
    expect(screen.getByRole("tab", { name: /pulseA/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /pulseA delete/i }));

    rows = screen.getAllByTestId(/job-row-/);
    expect(rows).toHaveLength(1);
    expect(screen.queryByRole("tab", { name: /pulseA/i })).not.toBeInTheDocument();
  });
});

function createWorkspaceFetchMock() {
  const runConfigs = new Map<string, ReturnType<typeof createDefaultConfig>>();
  let runCount = 0;

  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost:8000");
    const method = init?.method ?? "GET";

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

    const observableMatch = url.pathname.match(/^\/api\/v1\/runs\/([^/]+)\/observables\/([^/]+)$/);
    if (observableMatch && method === "GET") {
      const [, runId, observable] = observableMatch;
      const config = runConfigs.get(runId);
      if (!config) {
        return Promise.resolve(jsonResponse(404, { detail: "run not found" }));
      }
      return Promise.resolve(jsonResponse(200, buildObservablePayload(runId, observable, config)));
    }

    throw new Error(`unexpected fetch ${method} ${url.pathname}`);
  });
}

function buildRunDetail(runId: string, config: ReturnType<typeof createDefaultConfig>) {
  return {
    run_id: runId,
    name: config.name,
    solver: config.solver,
    state: "succeeded",
    created_at: "2026-03-16T00:00:00Z",
    updated_at: "2026-03-16T00:00:00Z",
    started_at: "2026-03-16T00:00:00Z",
    finished_at: "2026-03-16T00:00:01Z",
    status_message: "completed",
    lattice: {
      nx: config.lattice.nx,
      ny: config.lattice.ny,
    },
    time_grid: {
      dt: config.time.dt,
      t_final: config.time.t_final,
    },
    available_observables: [
      {
        name: "density",
        time_key: "time",
        series: [{ label: "mean", key: "mean" }],
        units: null,
        metadata: {},
      },
      {
        name: "energy",
        time_key: "time",
        series: [{ label: "total", key: "total" }],
        units: null,
        metadata: {},
      },
    ],
    diagnostics_excerpt: {
      site_count: config.lattice.nx * config.lattice.ny,
    },
    config,
    diagnostics: {
      site_count: config.lattice.nx * config.lattice.ny,
      dt: config.time.dt,
    },
  };
}

function buildObservablePayload(
  runId: string,
  observable: string,
  config: ReturnType<typeof createDefaultConfig>,
) {
  if (observable === "density") {
    return {
      name: "density",
      time: [0, config.time.dt, config.time.dt * 2],
      series: [
        {
          label: "mean",
          values: [0.5, 0.5 + runOffset(runId), 0.5 + runOffset(runId) * 2],
        },
      ],
      units: null,
      metadata: { solver: config.solver },
    };
  }

  return {
    name: "energy",
    time: [0, config.time.dt, config.time.dt * 2],
    series: [
      {
        label: "total",
        values: [-2.0, -1.9 + runOffset(runId), -1.8 + runOffset(runId)],
      },
    ],
    units: null,
    metadata: { solver: config.solver },
  };
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
