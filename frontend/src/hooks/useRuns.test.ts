import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRuns } from "./useRuns";
import { cancelRun, createRun, getRun, listRuns } from "../api/client";

vi.mock("../api/client", () => ({
  listRuns: vi.fn(),
  getRun: vi.fn(),
  createRun: vi.fn(),
  cancelRun: vi.fn(),
}));

function makeRunSummary(state: "queued" | "running" | "succeeded" | "succeeded_with_warnings" | "failed" | "cancelled") {
  return {
    run_id: "run-1",
    name: "run-1",
    solver: "tdhfb",
    state,
    created_at: "2026-03-23T00:00:00Z",
    updated_at: "2026-03-23T00:00:01Z",
    status_message: state === "running" ? "simulation running" : "simulation completed",
  };
}

function makeRunDetail(state: "queued" | "running" | "succeeded" | "succeeded_with_warnings" | "failed" | "cancelled") {
  return {
    run_id: "run-1",
    name: "run-1",
    solver: "tdhfb",
    state,
    created_at: "2026-03-23T00:00:00Z",
    updated_at: "2026-03-23T00:00:01Z",
    started_at: "2026-03-23T00:00:00Z",
    finished_at: state === "running" || state === "queued" ? null : "2026-03-23T00:00:02Z",
    status_message: state === "running" ? "simulation running" : "simulation completed",
    lattice: { nx: 2, ny: 2 },
    time_grid: { dt: 0.1, t_final: 0.2 },
    available_observables: [],
    diagnostics_excerpt: {},
    diagnostics: {},
    config: { solver: "tdhfb", representation: "real_space" },
  };
}

describe("useRuns polling lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(createRun).mockResolvedValue(makeRunDetail("succeeded") as any);
    vi.mocked(cancelRun).mockResolvedValue(makeRunDetail("cancelled") as any);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("does not continue polling after succeeded_with_warnings", async () => {
    vi.mocked(listRuns).mockResolvedValue([makeRunSummary("succeeded_with_warnings")] as any);
    vi.mocked(getRun).mockResolvedValue(makeRunDetail("succeeded_with_warnings") as any);

    renderHook(() => useRuns("run-1"));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const initialListRunsCalls = vi.mocked(listRuns).mock.calls.length;
    const initialGetRunCalls = vi.mocked(getRun).mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(vi.mocked(listRuns).mock.calls.length).toBe(initialListRunsCalls);
    expect(vi.mocked(getRun).mock.calls.length).toBe(initialGetRunCalls);
  });

  it("continues polling while run is running", async () => {
    vi.mocked(listRuns).mockResolvedValue([makeRunSummary("running")] as any);
    vi.mocked(getRun).mockResolvedValue(makeRunDetail("running") as any);

    renderHook(() => useRuns("run-1"));

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const initialListRunsCalls = vi.mocked(listRuns).mock.calls.length;
    const initialGetRunCalls = vi.mocked(getRun).mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(vi.mocked(listRuns).mock.calls.length).toBeGreaterThan(initialListRunsCalls);
    expect(vi.mocked(getRun).mock.calls.length).toBeGreaterThan(initialGetRunCalls);
  });
});
