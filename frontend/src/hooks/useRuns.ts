import { useEffect, useState } from "react";

import { cancelRun as apiCancelRun, createRun as apiCreateRun, getRun, listRuns } from "../api/client";
import type { RunDetail, RunSummary, SimulationConfigInput } from "../api/types";
import { formatRunSubmitError, isTerminalState, sortRuns, toErrorMessage } from "../lib/helpers";

const POLL_INTERVAL_MS = 1500;

export type UseRunsReturn = {
  runs: RunSummary[];
  runsLoading: boolean;
  runsError: string | null;
  selectedRunId: string | null;
  selectedRun: RunDetail | null;
  runLoading: boolean;
  runError: string | null;
  isSubmitting: boolean;
  isCancelling: boolean;
  submitError: string | null;
  cancelError: string | null;
  setSelectedRunId: (id: string | null) => void;
  createRun: (config: SimulationConfigInput) => Promise<void>;
  cancelRun: () => Promise<void>;
  refresh: () => void;
};

export function useRuns(initialRunId: string | null): UseRunsReturn {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setRunsLoading(true);

    listRuns()
      .then((items) => {
        if (!active) return;
        setRuns(sortRuns(items));
        setRunsError(null);
      })
      .catch((error) => {
        if (!active) return;
        setRunsError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) setRunsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [refreshVersion]);

  useEffect(() => {
    if (runs.length === 0) {
      setSelectedRunId(null);
      return;
    }

    const hasSelectedRun = selectedRunId ? runs.some((run) => run.run_id === selectedRunId) : false;
    if (!hasSelectedRun) {
      setSelectedRunId(runs[0].run_id);
    }
  }, [runs, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      setRunError(null);
      return;
    }

    let active = true;
    setRunLoading(true);

    getRun(selectedRunId)
      .then((run) => {
        if (!active) return;
        setSelectedRun(run);
        setRunError(null);
      })
      .catch((error) => {
        if (!active) return;
        setRunError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) setRunLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, refreshVersion]);

  useEffect(() => {
    if (!selectedRun || isTerminalState(selectedRun.state)) {
      return;
    }

    const timer = window.setInterval(() => {
      setRefreshVersion((current) => current + 1);
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [selectedRun]);

  async function handleCreateRun(config: SimulationConfigInput) {
    setIsSubmitting(true);
    setSubmitError(null);
    setCancelError(null);

    try {
      const run = await apiCreateRun(config);
      setSelectedRun(run);
      setSelectedRunId(run.run_id);
      setRefreshVersion((current) => current + 1);
    } catch (error) {
      setSubmitError(formatRunSubmitError(error, config));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCancelRun() {
    if (!selectedRunId || !selectedRun || isTerminalState(selectedRun.state)) {
      return;
    }

    setIsCancelling(true);
    setCancelError(null);

    try {
      const run = await apiCancelRun(selectedRunId);
      setSelectedRun(run);
      setRefreshVersion((current) => current + 1);
    } catch (error) {
      setCancelError(toErrorMessage(error));
    } finally {
      setIsCancelling(false);
    }
  }

  function refresh() {
    setRefreshVersion((current) => current + 1);
  }

  return {
    runs,
    runsLoading,
    runsError,
    selectedRunId,
    selectedRun,
    runLoading,
    runError,
    isSubmitting,
    isCancelling,
    submitError,
    cancelError,
    setSelectedRunId,
    createRun: handleCreateRun,
    cancelRun: handleCancelRun,
    refresh,
  };
}
