import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import { useDerivedAnalysis } from "./useDerivedAnalysis";

vi.mock("../api/client", () => {
  return {
    ApiError: class MockApiError extends Error {
      status: number;
      payload?: unknown;
      constructor(status: number, message: string, payload?: unknown) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.payload = payload;
      }
    },
    getDerivedAnalysis: vi.fn(),
    getDerivedAnalysisResult: vi.fn(),
    launchDerivedAnalysis: vi.fn(),
    listDerivedAnalyses: vi.fn(),
  };
});

import {
  getDerivedAnalysisResult,
  launchDerivedAnalysis,
  listDerivedAnalyses,
} from "../api/client";

describe("useDerivedAnalysis", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("fails fast on 404 source-not-found and shows actionable message", async () => {
    vi.mocked(listDerivedAnalyses).mockResolvedValue([]);
    vi.mocked(launchDerivedAnalysis).mockRejectedValue(
      new ApiError(404, "derived analysis source not found"),
    );

    const { result } = renderHook(() =>
      useDerivedAnalysis("run", "run-001", "k_spectral_preview"),
    );

    await act(async () => {
      await result.current.launch();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("failed");
      expect(result.current.error).toContain("Derived analysis source not found.");
      expect(result.current.error).toContain("frontend/backend versions are mismatched");
    });
  });

  it("maps 422 study_id errors to a version-mismatch hint", async () => {
    vi.mocked(listDerivedAnalyses).mockResolvedValue([]);
    vi.mocked(launchDerivedAnalysis).mockRejectedValue(
      new ApiError(422, "study_id not found"),
    );

    const { result } = renderHook(() =>
      useDerivedAnalysis("run", "run-001", "tr_arpes_preview"),
    );

    await act(async () => {
      await result.current.launch();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("failed");
      expect(result.current.error).toContain("backend rejected study_id");
      expect(result.current.error).toContain("version mismatch");
    });
  });

  it("does not reuse cached analyses when parameters differ", async () => {
    vi.mocked(listDerivedAnalyses).mockResolvedValue([
      {
        analysis_id: "analysis-cached",
        study_id: "__none__",
        source_kind: "run",
        source_id: "run-001",
        analysis_type: "fft_preview",
        analysis_version: "v1",
        cache_key: "cached",
        parameters: { observable: "energy" },
        status: "succeeded",
        input_surface_ids: [],
        result_metadata: {},
        data_refs: [],
        supports_bundle_ids: [],
        created_at: "2026-03-25T00:00:00Z",
        updated_at: "2026-03-25T00:00:00Z",
      },
    ]);
    vi.mocked(launchDerivedAnalysis).mockResolvedValue({
      analysis_id: "analysis-fresh",
      study_id: "__none__",
      source_kind: "run",
      source_id: "run-001",
      analysis_type: "fft_preview",
      analysis_version: "v1",
      cache_key: "fresh",
      parameters: { observable: "current_x" },
      status: "succeeded",
      input_surface_ids: [],
      result_metadata: {},
      data_refs: [],
      supports_bundle_ids: [],
      created_at: "2026-03-25T00:00:00Z",
      updated_at: "2026-03-25T00:00:00Z",
    });
    vi.mocked(getDerivedAnalysisResult).mockResolvedValue({
      analysis: {
        analysis_id: "analysis-fresh",
        study_id: "__none__",
        source_kind: "run",
        source_id: "run-001",
        analysis_type: "fft_preview",
        analysis_version: "v1",
        cache_key: "fresh",
        parameters: { observable: "current_x" },
        status: "succeeded",
        input_surface_ids: [],
        result_metadata: {},
        data_refs: [],
        supports_bundle_ids: [],
        created_at: "2026-03-25T00:00:00Z",
        updated_at: "2026-03-25T00:00:00Z",
      },
      payload_kind: "observable",
      payload: {
        name: "current_x_fft_preview",
        time: [0, 1],
        series: [{ label: "total magnitude", values: [0, 1] }],
        units: null,
        metadata: {},
      },
    });

    const { result } = renderHook(() =>
      useDerivedAnalysis("run", "run-001", "fft_preview", {
        parameters: { observable: "current_x" },
      }),
    );

    await act(async () => {
      await result.current.launch();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("succeeded");
    });

    expect(listDerivedAnalyses).toHaveBeenCalledWith({
      study_id: "__none__",
      source_kind: "run",
      source_id: "run-001",
    });
    expect(launchDerivedAnalysis).toHaveBeenCalledWith(
      expect.objectContaining({
        parameters: { observable: "current_x" },
      }),
    );
    expect(getDerivedAnalysisResult).toHaveBeenCalledWith("analysis-fresh");
  });

  it("resets to idle when analysis parameters change", async () => {
    vi.mocked(listDerivedAnalyses).mockResolvedValue([]);
    vi.mocked(launchDerivedAnalysis).mockResolvedValue({
      analysis_id: "analysis-001",
      study_id: "__none__",
      source_kind: "run",
      source_id: "run-001",
      analysis_type: "fft_preview",
      analysis_version: "v1",
      cache_key: "fresh",
      parameters: { observable: "energy" },
      status: "succeeded",
      input_surface_ids: [],
      result_metadata: {},
      data_refs: [],
      supports_bundle_ids: [],
      created_at: "2026-03-25T00:00:00Z",
      updated_at: "2026-03-25T00:00:00Z",
    });
    vi.mocked(getDerivedAnalysisResult).mockResolvedValue({
      analysis: {
        analysis_id: "analysis-001",
        study_id: "__none__",
        source_kind: "run",
        source_id: "run-001",
        analysis_type: "fft_preview",
        analysis_version: "v1",
        cache_key: "fresh",
        parameters: { observable: "energy" },
        status: "succeeded",
        input_surface_ids: [],
        result_metadata: {},
        data_refs: [],
        supports_bundle_ids: [],
        created_at: "2026-03-25T00:00:00Z",
        updated_at: "2026-03-25T00:00:00Z",
      },
      payload_kind: "observable",
      payload: {
        name: "energy_fft_preview",
        time: [0, 1],
        series: [{ label: "total magnitude", values: [0, 1] }],
        units: null,
        metadata: {},
      },
    });

    const { result, rerender } = renderHook(
      ({ observable }) =>
        useDerivedAnalysis("run", "run-001", "fft_preview", {
          parameters: { observable },
        }),
      { initialProps: { observable: "energy" } },
    );

    await act(async () => {
      await result.current.launch();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("succeeded");
    });

    rerender({ observable: "current_x" });

    await waitFor(() => {
      expect(result.current.status).toBe("idle");
      expect(result.current.result).toBeNull();
    });
  });
});
