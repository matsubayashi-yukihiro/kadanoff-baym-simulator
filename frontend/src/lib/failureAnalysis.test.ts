import { describe, expect, it } from "vitest";
import { analyzeFailure } from "./failureAnalysis";
import type { RunDetail } from "../api/types";

function makeRun(overrides: Partial<RunDetail>): RunDetail {
  return {
    run_id: "test-001",
    name: "test",
    solver: "noninteracting",
    state: "succeeded",
    created_at: "2026-03-17T00:00:00Z",
    updated_at: "2026-03-17T00:00:00Z",
    status_message: "",
    config: {} as RunDetail["config"],
    ...overrides,
  } as RunDetail;
}

describe("analyzeFailure", () => {
  it("returns null for succeeded runs", () => {
    expect(analyzeFailure(makeRun({ state: "succeeded" }))).toBeNull();
  });

  it("classifies cancelled runs", () => {
    const result = analyzeFailure(makeRun({ state: "cancelled" }));
    expect(result?.category).toBe("cancelled");
  });

  it("classifies NaN solver errors", () => {
    const result = analyzeFailure(makeRun({ state: "failed", status_message: "NaN detected at step 42" }));
    expect(result?.category).toBe("solver_error");
    expect(result?.summary).toContain("NaN");
  });

  it("classifies convergence failures", () => {
    const result = analyzeFailure(makeRun({ state: "failed", status_message: "Fixed-point did not converge" }));
    expect(result?.category).toBe("solver_error");
    expect(result?.summary).toContain("converge");
  });

  it("classifies timeout", () => {
    const result = analyzeFailure(makeRun({ state: "failed", status_message: "Run timed out after 300s" }));
    expect(result?.category).toBe("timeout");
  });

  it("classifies validation errors", () => {
    const result = analyzeFailure(makeRun({ state: "failed", status_message: "validation failed: invalid dt" }));
    expect(result?.category).toBe("validation_error");
  });

  it("falls back to unknown", () => {
    const result = analyzeFailure(makeRun({ state: "failed", status_message: "something weird" }));
    expect(result?.category).toBe("unknown");
  });
});
