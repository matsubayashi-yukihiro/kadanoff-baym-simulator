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
});
