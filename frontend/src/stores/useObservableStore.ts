import { create } from "zustand";

import { getObservable, listObservables } from "../api/client";
import type { ObservableCatalogResponse, ObservableResponse } from "../api/types";
import { toErrorMessage } from "../lib/helpers";

type ObservableState = {
  catalog: ObservableCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedObservable: string | null;
  data: ObservableResponse | null;
  dataLoading: boolean;
  dataError: string | null;
  overlayNames: Set<string>;
  overlayData: Map<string, ObservableResponse>;

  setSelectedObservable: (name: string) => void;
  toggleOverlay: (name: string) => void;
  fetchCatalog: (runId: string) => Promise<void>;
  fetchData: (runId: string, name: string) => Promise<void>;
  fetchOverlay: (runId: string, name: string) => Promise<void>;
  resetForRun: () => void;
};

export const useObservableStore = create<ObservableState>()((set, get) => ({
  catalog: null,
  catalogLoading: false,
  catalogError: null,
  selectedObservable: null,
  data: null,
  dataLoading: false,
  dataError: null,
  overlayNames: new Set(),
  overlayData: new Map(),

  setSelectedObservable: (name) => set({ selectedObservable: name }),

  toggleOverlay: (name) => {
    const prev = get().overlayNames;
    const next = new Set(prev);
    if (next.has(name)) {
      next.delete(name);
      const nextData = new Map(get().overlayData);
      nextData.delete(name);
      set({ overlayNames: next, overlayData: nextData });
    } else {
      next.add(name);
      set({ overlayNames: next });
    }
  },

  fetchCatalog: async (runId) => {
    set({ catalogLoading: true });
    try {
      const result = await listObservables(runId);
      set({ catalog: result, catalogError: null });
      const names = result.observables ?? [];
      const { selectedObservable } = get();
      if (names.length > 0 && (!selectedObservable || !names.includes(selectedObservable))) {
        set({ selectedObservable: names[0] });
      }
    } catch (error) {
      set({ catalog: null, catalogError: toErrorMessage(error) });
    } finally {
      set({ catalogLoading: false });
    }
  },

  fetchData: async (runId, name) => {
    set({ dataLoading: true });
    try {
      const result = await getObservable(runId, name);
      set({ data: result, dataError: null });
    } catch (error) {
      set({ data: null, dataError: toErrorMessage(error) });
    } finally {
      set({ dataLoading: false });
    }
  },

  fetchOverlay: async (runId, name) => {
    try {
      const result = await getObservable(runId, name);
      set({ overlayData: new Map(get().overlayData).set(name, result) });
    } catch {
      // silently ignore overlay fetch failures
    }
  },

  resetForRun: () =>
    set({
      catalog: null,
      catalogError: null,
      selectedObservable: null,
      data: null,
      dataError: null,
      overlayNames: new Set(),
      overlayData: new Map(),
    }),
}));
