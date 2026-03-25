import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RunProgressRecord } from "../api/types";

import { useRunProgress } from "./useRunProgress";

vi.mock("../api/client", () => ({
  ApiError: class MockApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = "ApiError";
    }
  },
  getRunProgress: vi.fn(),
}));

import { getRunProgress } from "../api/client";

const baseProgress: RunProgressRecord = {
  run_id: "run-1",
  state: "running" as const,
  phase: "propagating",
  updated_at: "2026-03-21T00:00:00Z",
  started_at: "2026-03-21T00:00:00Z",
  wall_seconds_elapsed: 1,
  physical_time_current: 0.1,
  physical_time_final: 1,
  physical_progress_fraction: 0.1,
  accepted_steps: 1,
  requested_steps: 10,
  rejected_steps: 0,
  saved_samples_written: 1,
  status_line: "running",
  solver_metrics: {},
  history: [],
};

describe("useRunProgress", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-21T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("does not mark stale only because backend updated_at is old", async () => {
    vi.mocked(getRunProgress).mockImplementation(async () => ({
      ...baseProgress,
      updated_at: "2026-03-20T23:59:00Z",
    }));

    const { result } = renderHook(() => useRunProgress("run-1", true));

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.progress).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    expect(result.current.isStale).toBe(false);
  });

  it("marks stale when no progress fields change for long enough", async () => {
    vi.mocked(getRunProgress).mockImplementation(async () => ({
      ...baseProgress,
      updated_at: "2026-03-20T23:59:00Z",
    }));

    const { result } = renderHook(() => useRunProgress("run-1", true));

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.progress).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(32000);
    });

    expect(result.current.isStale).toBe(true);
  });

  it("uses a longer stale threshold while finalizing", async () => {
    vi.mocked(getRunProgress).mockImplementation(async () => ({
      ...baseProgress,
      phase: "finalizing",
      status_line: "finalizing: writing artifacts",
    }));

    const { result } = renderHook(() => useRunProgress("run-1", true));

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.progress).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    expect(result.current.isStale).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(122000);
    });
    expect(result.current.isStale).toBe(true);
    expect(result.current.staleDetails?.phase).toBe("finalizing");
  });

  it("marks stale when polling stops succeeding", async () => {
    vi.mocked(getRunProgress)
      .mockResolvedValueOnce({ ...baseProgress })
      .mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useRunProgress("run-1", true));

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.progress).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000);
    });

    expect(result.current.isStale).toBe(true);
  });
});
