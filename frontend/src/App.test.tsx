import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";
import { createDefaultConfig } from "./lib/defaultConfig";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("creates a run and loads density, energy, and current_x plots", async () => {
    const runId = "run-e2e-001";
    let listRunsCallCount = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input));
        const method = init?.method ?? "GET";

        if (url.pathname === "/api/v1/runs" && method === "GET") {
          listRunsCallCount += 1;
          return Promise.resolve(jsonResponse(200, listRunsCallCount === 1 ? [] : [buildRunSummary(runId)]));
        }

        if (url.pathname === "/api/v1/runs" && method === "POST") {
          return Promise.resolve(jsonResponse(202, buildRunDetail(runId)));
        }

        if (url.pathname === `/api/v1/runs/${runId}` && method === "GET") {
          return Promise.resolve(jsonResponse(200, buildRunDetail(runId)));
        }

        if (url.pathname === `/api/v1/runs/${runId}/observables` && method === "GET") {
          return Promise.resolve(
            jsonResponse(200, {
              run_id: runId,
              observables: ["density", "energy", "current_x"],
            }),
          );
        }

        if (url.pathname === `/api/v1/runs/${runId}/observables/density` && method === "GET") {
          return Promise.resolve(
            jsonResponse(200, {
              name: "density",
              time: [0, 0.1, 0.2],
              series: [
                { label: "mean", values: [0.5, 0.5, 0.5] },
                { label: "min", values: [0.48, 0.48, 0.48] },
                { label: "max", values: [0.52, 0.52, 0.52] },
              ],
              units: null,
              metadata: { solver: "noninteracting" },
            }),
          );
        }

        if (url.pathname === `/api/v1/runs/${runId}/observables/energy` && method === "GET") {
          return Promise.resolve(
            jsonResponse(200, {
              name: "energy",
              time: [0, 0.1, 0.2],
              series: [{ label: "total", values: [-2.0, -1.95, -1.9] }],
              units: null,
              metadata: { solver: "noninteracting" },
            }),
          );
        }

        if (url.pathname === `/api/v1/runs/${runId}/observables/current_x` && method === "GET") {
          return Promise.resolve(
            jsonResponse(200, {
              name: "current_x",
              time: [0, 0.1, 0.2],
              series: [{ label: "total", values: [0.0, 0.05, 0.04] }],
              units: null,
              metadata: { solver: "noninteracting" },
            }),
          );
        }

        throw new Error(`unexpected fetch ${method} ${url.pathname}`);
      }) as unknown as typeof fetch,
    );

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("No saved runs yet.");
    await user.click(screen.getByRole("button", { name: "Create Run" }));

    await screen.findByText(runId);
    await screen.findByRole("img", { name: "observable-chart-density" });
    await screen.findByText("Site Count");
    expect(screen.getByRole("button", { name: "Energy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Current X" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Energy" }));
    await screen.findByRole("img", { name: "observable-chart-energy" });

    await user.click(screen.getByRole("button", { name: "Current X" }));
    await screen.findByRole("img", { name: "observable-chart-current_x" });

    await waitFor(() => {
      expect(screen.getByText("0.0025")).toBeInTheDocument();
    });
  });
});

function buildRunSummary(runId: string) {
  return {
    run_id: runId,
    name: "square-4x4-baseline",
    solver: "noninteracting",
    state: "succeeded",
    created_at: "2026-03-15T00:00:00Z",
    updated_at: "2026-03-15T00:00:02Z",
    started_at: "2026-03-15T00:00:00Z",
    finished_at: "2026-03-15T00:00:02Z",
    status_message: "run finished",
    lattice: { nx: 4, ny: 4 },
    time_grid: { dt: 0.1, t_final: 0.2 },
    available_observables: [
      { name: "density", time_key: "density__time", series: [{ label: "mean", key: "density__mean" }], units: null, metadata: {} },
      { name: "energy", time_key: "energy__time", series: [{ label: "total", key: "energy__total" }], units: null, metadata: {} },
      {
        name: "current_x",
        time_key: "current_x__time",
        series: [{ label: "total", key: "current_x__total" }],
        units: null,
        metadata: {},
      },
    ],
    diagnostics_excerpt: {
      final_energy: -1.9,
      final_density: 0.5,
    },
  };
}

function buildRunDetail(runId: string) {
  return {
    ...buildRunSummary(runId),
    config: createDefaultConfig(),
    diagnostics: {
      site_count: 16,
      time_steps: 2,
      energy_drift: 0.0025,
    },
  };
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
