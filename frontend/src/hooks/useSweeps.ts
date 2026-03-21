import { useCallback, useEffect, useRef, useState } from "react";
import { getSweep, launchSweep, listSweeps } from "../api/client";
import type { SweepLaunchRequest, SweepRecord } from "../api/types";

type SweepsState = {
  sweeps: SweepRecord[];
  loading: boolean;
  error: string | null;
  selectedSweepId: string | null;
  selectedSweep: SweepRecord | null;
  sweepLoading: boolean;
  sweepError: string | null;
  isLaunching: boolean;
  launchError: string | null;
};

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);
const POLL_INTERVAL_MS = 2000;

export function useSweeps(studyId?: string | null) {
  const [state, setState] = useState<SweepsState>({
    sweeps: [],
    loading: false,
    error: null,
    selectedSweepId: null,
    selectedSweep: null,
    sweepLoading: false,
    sweepError: null,
    isLaunching: false,
    launchError: null,
  });

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const fetchSweeps = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const sweeps = await listSweeps(studyId ? { study_id: studyId } : {});
      if (!mountedRef.current) return;
      setState((prev) => ({ ...prev, sweeps, loading: false }));
    } catch (err) {
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "failed to load sweeps",
      }));
    }
  }, [studyId]);

  const pollSweep = useCallback(async (sweepId: string) => {
    if (!mountedRef.current) return;
    try {
      const sweep = await getSweep(sweepId);
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        selectedSweep: sweep,
        sweepLoading: false,
        sweeps: prev.sweeps.map((s) => (s.sweep_id === sweepId ? sweep : s)),
      }));
      if (!TERMINAL_STATES.has(sweep.state)) {
        pollTimerRef.current = setTimeout(() => pollSweep(sweepId), POLL_INTERVAL_MS);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        sweepLoading: false,
        sweepError: err instanceof Error ? err.message : "failed to fetch sweep",
      }));
    }
  }, []);

  const selectSweep = useCallback(
    (sweepId: string) => {
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setState((prev) => ({
        ...prev,
        selectedSweepId: sweepId,
        selectedSweep: prev.sweeps.find((s) => s.sweep_id === sweepId) ?? null,
        sweepLoading: true,
        sweepError: null,
      }));
      pollSweep(sweepId);
    },
    [pollSweep],
  );

  const launchSweepRequest = useCallback(
    async (req: SweepLaunchRequest) => {
      setState((prev) => ({ ...prev, isLaunching: true, launchError: null }));
      try {
        const sweep = await launchSweep(req);
        if (!mountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isLaunching: false,
          sweeps: [sweep, ...prev.sweeps],
          selectedSweepId: sweep.sweep_id,
          selectedSweep: sweep,
        }));
        pollSweep(sweep.sweep_id);
      } catch (err) {
        if (!mountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isLaunching: false,
          launchError: err instanceof Error ? err.message : "launch failed",
        }));
      }
    },
    [pollSweep],
  );

  useEffect(() => {
    fetchSweeps();
  }, [fetchSweeps]);

  return {
    ...state,
    fetchSweeps,
    selectSweep,
    launchSweep: launchSweepRequest,
  };
}
