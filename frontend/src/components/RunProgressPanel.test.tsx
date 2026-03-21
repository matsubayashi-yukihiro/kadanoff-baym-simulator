import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import type { RunDetail, RunProgressRecord } from "../api/types";
import { RunProgressPanel } from "./RunProgressPanel";

function makeRun(state: "queued" | "running" = "running"): RunDetail {
  return {
    run_id: "run-1",
    name: "debug-run",
    solver: "noninteracting",
    state,
    created_at: "2026-03-21T00:00:00Z",
    updated_at: "2026-03-21T00:00:00Z",
    started_at: "2026-03-21T00:00:01Z",
    finished_at: null,
    status_message: "simulation running",
    lattice: {
      kind: "square",
      nx: 2,
      ny: 2,
      boundary: "periodic",
      hopping: 1,
      chemical_potential: 0,
    },
    time_grid: {
      t_final: 1,
      dt: 0.1,
      save_every: 1,
    },
    available_observables: [],
    diagnostics_excerpt: {},
    config: {
      name: "debug-run",
      solver: "noninteracting",
      representation: "real_space",
      lattice: {
        kind: "square",
        nx: 2,
        ny: 2,
        boundary: "periodic",
        hopping: 1,
        chemical_potential: 0,
      },
      time: {
        t_final: 1,
        dt: 0.1,
        save_every: 1,
      },
      drive: {
        drive_type: "gaussian",
        amplitude_x: 0,
        amplitude_y: 0,
        frequency: 0,
        phase: 0,
        center: 0,
        width: 1,
      },
      interaction: {
        onsite_u: 0,
        nearest_neighbor_v: 0,
        pairing_channel: "none",
      },
      initial_state: {
        filling: 0.5,
        temperature: 0,
        seed_pairing: 0,
      },
      kbe: {
        self_energy: "hfb",
        max_fixed_point_iterations: 6,
        tolerance: 1e-7,
        mixing: 0.35,
        memory_window: null,
      },
      adaptive: {
        enabled: false,
        atol: 1e-7,
        rtol: 1e-5,
        min_dt: null,
        max_dt: null,
        max_growth: 2,
        min_shrink: 0.25,
      },
      thermal_branch: {
        enabled: false,
        n_tau: 16,
        max_iterations: 8,
        mixing: 0.3,
      },
      observables: ["density"],
    },
    diagnostics: {},
  };
}

function makeProgress(): RunProgressRecord {
  return {
    run_id: "run-1",
    state: "running",
    phase: "propagating",
    updated_at: "2026-03-21T00:00:02Z",
    started_at: "2026-03-21T00:00:01Z",
    wall_seconds_elapsed: 1,
    physical_time_current: 0.2,
    physical_time_final: 1,
    physical_progress_fraction: 0.2,
    accepted_steps: 2,
    requested_steps: 10,
    rejected_steps: 0,
    saved_samples_written: 2,
    status_line: "simulation running",
    solver_metrics: {},
    history: [],
  };
}

describe("RunProgressPanel", () => {
  it("shows an explicit backend error state when progress fetch fails", () => {
    render(
      <RunProgressPanel
        run={makeRun()}
        progress={null}
        loading={false}
        error="run not found"
        isStale={false}
      />,
    );

    expect(screen.getByText("Progress telemetry is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("No progress telemetry yet.")).not.toBeInTheDocument();
  });

  it("keeps the empty telemetry hint when there is no error yet", () => {
    render(
      <RunProgressPanel
        run={makeRun("queued")}
        progress={null}
        loading={false}
        error={null}
        isStale={false}
      />,
    );

    expect(screen.getByText("No progress telemetry yet.")).toBeInTheDocument();
  });

  it("renders telemetry when progress exists", () => {
    render(
      <RunProgressPanel
        run={makeRun()}
        progress={makeProgress()}
        loading={false}
        error={null}
        isStale={false}
      />,
    );

    expect(screen.getByText("Live Run Progress")).toBeInTheDocument();
    expect(screen.getByText("simulation running")).toBeInTheDocument();
  });
});
