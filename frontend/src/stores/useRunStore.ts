import { create } from "zustand";

import {
  cancelRun as apiCancelRun,
  createRun as apiCreateRun,
  getRun,
  listRuns,
} from "../api/client";
import type { RunDetail, RunSummary, SimulationConfigInput } from "../api/types";
import { formatRunSubmitError, isTerminalState, sortRuns, toErrorMessage } from "../lib/helpers";

type RunState = {
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
  fetchRuns: () => Promise<void>;
  fetchSelectedRun: () => Promise<void>;
  createRun: (config: SimulationConfigInput) => Promise<void>;
  cancelRun: () => Promise<void>;
  refresh: () => void;
  startPolling: () => () => void;
};

export const useRunStore = create<RunState>()((set, get) => ({
  runs: [],
  runsLoading: true,
  runsError: null,
  selectedRunId: null,
  selectedRun: null,
  runLoading: false,
  runError: null,
  isSubmitting: false,
  isCancelling: false,
  submitError: null,
  cancelError: null,

  setSelectedRunId: (id) => set({ selectedRunId: id }),

  fetchRuns: async () => {
    set({ runsLoading: true });
    try {
      const items = await listRuns();
      const sorted = sortRuns(items);
      set({ runs: sorted, runsError: null });

      const { selectedRunId } = get();
      if (sorted.length === 0) {
        set({ selectedRunId: null });
      } else if (!selectedRunId || !sorted.some((r) => r.run_id === selectedRunId)) {
        set({ selectedRunId: sorted[0].run_id });
      }
    } catch (error) {
      set({ runsError: toErrorMessage(error) });
    } finally {
      set({ runsLoading: false });
    }
  },

  fetchSelectedRun: async () => {
    const { selectedRunId } = get();
    if (!selectedRunId) {
      set({ selectedRun: null, runError: null });
      return;
    }

    set({ runLoading: true });
    try {
      const run = await getRun(selectedRunId);
      set({ selectedRun: run, runError: null });
    } catch (error) {
      set({ runError: toErrorMessage(error) });
    } finally {
      set({ runLoading: false });
    }
  },

  createRun: async (config) => {
    set({ isSubmitting: true, submitError: null, cancelError: null });
    try {
      const run = await apiCreateRun(config);
      set({ selectedRun: run, selectedRunId: run.run_id });
      await get().fetchRuns();
    } catch (error) {
      set({ submitError: formatRunSubmitError(error, config) });
    } finally {
      set({ isSubmitting: false });
    }
  },

  cancelRun: async () => {
    const { selectedRunId, selectedRun } = get();
    if (!selectedRunId || !selectedRun || isTerminalState(selectedRun.state)) return;

    set({ isCancelling: true, cancelError: null });
    try {
      const run = await apiCancelRun(selectedRunId);
      set({ selectedRun: run });
      await get().fetchRuns();
      await get().fetchSelectedRun();
    } catch (error) {
      set({ cancelError: toErrorMessage(error) });
    } finally {
      set({ isCancelling: false });
    }
  },

  refresh: () => {
    get().fetchRuns();
    get().fetchSelectedRun();
  },

  startPolling: () => {
    let tick = 0;
    const timer = window.setInterval(() => {
      const { selectedRun } = get();
      if (selectedRun && !isTerminalState(selectedRun.state)) {
        get().fetchSelectedRun();
        if (tick % 5 === 0) {
          get().fetchRuns();
        }
        tick++;
      }
    }, 3000);
    return () => window.clearInterval(timer);
  },
}));
