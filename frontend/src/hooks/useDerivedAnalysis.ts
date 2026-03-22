import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  getDerivedAnalysis,
  getDerivedAnalysisResult,
  launchDerivedAnalysis,
  listDerivedAnalyses,
} from "../api/client";
import type {
  DerivedAnalysisArtifactRecord,
  DerivedAnalysisResultRecord,
  DerivedAnalysisSourceKind,
} from "../api/types";

type DerivedAnalysisState = {
  analysis: DerivedAnalysisArtifactRecord | null;
  result: DerivedAnalysisResultRecord | null;
  status: "idle" | "launching" | "polling" | "succeeded" | "failed";
  error: string | null;
};

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

function normalizeAnalysisType(sourceKind: DerivedAnalysisSourceKind, analysisType: string): string {
  const prefix = `${sourceKind}/`;
  return analysisType.startsWith(prefix) ? analysisType.slice(prefix.length) : analysisType;
}

function toDerivedAnalysisErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 404 && error.message.includes("derived analysis source not found")) {
    return "Derived analysis source not found. The selected run may be missing from backend registry, or frontend/backend versions are mismatched. Restart/rebuild backend and retry.";
  }
  if (error instanceof ApiError && error.status === 422 && error.message.includes("study_id not found")) {
    return "Derived analysis launch failed because the backend rejected study_id. This usually indicates frontend/backend version mismatch. Restart/rebuild backend and retry.";
  }
  if (error instanceof Error) return error.message;
  return "launch failed";
}

export function useDerivedAnalysis(
  sourceKind: DerivedAnalysisSourceKind | null,
  sourceId: string | null,
  analysisType: string | null,
  params: { study_id?: string; parameters?: Record<string, unknown> } = {},
) {
  const [state, setState] = useState<DerivedAnalysisState>({
    analysis: null,
    result: null,
    status: "idle",
    error: null,
  });

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortedRef = useRef(false);

  const clearPoll = () => {
    if (pollTimerRef.current !== null) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const pollUntilDone = useCallback(
    async (analysisId: string) => {
      if (abortedRef.current) return;

      try {
        const record = await getDerivedAnalysis(analysisId);
        if (abortedRef.current) return;

        if (TERMINAL_STATES.has(record.status)) {
          if (record.status === "succeeded") {
            const resultRecord = await getDerivedAnalysisResult(analysisId);
            if (!abortedRef.current) {
              setState({ analysis: record, result: resultRecord, status: "succeeded", error: null });
            }
          } else {
            setState({ analysis: record, result: null, status: "failed", error: `Analysis ${record.status}` });
          }
        } else {
          // Still running — schedule next poll
          pollTimerRef.current = setTimeout(() => pollUntilDone(analysisId), POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!abortedRef.current) {
          setState((prev) => ({
            ...prev,
            status: "failed",
            error: err instanceof Error ? err.message : "polling failed",
          }));
        }
      }
    },
    [],
  );

  const launch = useCallback(async () => {
    if (!sourceKind || !sourceId || !analysisType) return;
    const normalizedAnalysisType = normalizeAnalysisType(sourceKind, analysisType);

    abortedRef.current = false;
    clearPoll();

    setState({ analysis: null, result: null, status: "launching", error: null });

    try {
      const studyId = params.study_id ?? "__none__";

      // Check for an existing cached analysis
      const existing = await listDerivedAnalyses({
        source_kind: sourceKind,
        source_id: sourceId,
      });

      const cached = existing.find(
        (a) =>
          normalizeAnalysisType(sourceKind, a.analysis_type) === normalizedAnalysisType &&
          a.source_kind === sourceKind &&
          a.source_id === sourceId,
      );

      if (cached) {
        if (TERMINAL_STATES.has(cached.status)) {
          if (cached.status === "succeeded") {
            const resultRecord = await getDerivedAnalysisResult(cached.analysis_id);
            setState({ analysis: cached, result: resultRecord, status: "succeeded", error: null });
            return;
          }
          if (state.status !== "failed") {
            setState({
              analysis: cached,
              result: null,
              status: "failed",
              error: `Analysis ${cached.status}`,
            });
            return;
          }
        } else {
          // In-progress — poll from existing
          setState((prev) => ({ ...prev, analysis: cached, status: "polling" }));
          pollTimerRef.current = setTimeout(() => pollUntilDone(cached.analysis_id), POLL_INTERVAL_MS);
          return;
        }
      }

      // Launch fresh
      const newAnalysis = await launchDerivedAnalysis({
        study_id: studyId,
        source_kind: sourceKind,
        source_id: sourceId,
        analysis_type: normalizedAnalysisType,
        analysis_version: "v1",
        parameters: params.parameters ?? {},
      });

      if (abortedRef.current) return;

      setState((prev) => ({ ...prev, analysis: newAnalysis, status: "polling" }));

      if (TERMINAL_STATES.has(newAnalysis.status)) {
        if (newAnalysis.status === "succeeded") {
          const resultRecord = await getDerivedAnalysisResult(newAnalysis.analysis_id);
          setState({ analysis: newAnalysis, result: resultRecord, status: "succeeded", error: null });
        } else {
          setState({ analysis: newAnalysis, result: null, status: "failed", error: `Analysis ${newAnalysis.status}` });
        }
      } else {
        pollTimerRef.current = setTimeout(() => pollUntilDone(newAnalysis.analysis_id), POLL_INTERVAL_MS);
      }
    } catch (err) {
      if (!abortedRef.current) {
        setState({
          analysis: null,
          result: null,
          status: "failed",
          error: toDerivedAnalysisErrorMessage(err),
        });
      }
    }
  }, [sourceKind, sourceId, analysisType, params.study_id, params.parameters, pollUntilDone, state.status]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortedRef.current = true;
      clearPoll();
    };
  }, []);

  return { ...state, launch };
}
