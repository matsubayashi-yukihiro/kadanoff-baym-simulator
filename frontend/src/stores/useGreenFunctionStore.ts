import { create } from "zustand";

import {
  getGreenFunctionSlice,
  getMixedGreenFunctionSlice,
  getThermalBranchSlice,
  listGreenFunctions,
  listMixedGreenFunctions,
  listThermalBranch,
} from "../api/client";
import type {
  GreenFunctionCatalogResponse,
  GreenFunctionSliceResponse,
  MixedGreenFunctionCatalogResponse,
  MixedGreenFunctionSliceResponse,
  ThermalBranchCatalogResponse,
  ThermalBranchSliceResponse,
} from "../api/types";
import { clamp, toErrorMessage } from "../lib/helpers";

type GreenFunctionState = {
  // Real-time green functions
  catalog: GreenFunctionCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedComponent: string | null;
  rowIndex: number;
  colIndex: number;
  nambuStart: number;
  nambuWindow: number;
  slice: GreenFunctionSliceResponse | null;
  sliceLoading: boolean;
  sliceError: string | null;

  // Thermal branch
  thermalCatalog: ThermalBranchCatalogResponse | null;
  thermalCatalogLoading: boolean;
  thermalCatalogError: string | null;
  thermalComponent: string | null;
  tauIndex: number;
  thermalNambuStart: number;
  thermalNambuWindow: number;
  thermalSlice: ThermalBranchSliceResponse | null;
  thermalSliceLoading: boolean;
  thermalSliceError: string | null;

  // Mixed green functions
  mixedCatalog: MixedGreenFunctionCatalogResponse | null;
  mixedCatalogLoading: boolean;
  mixedCatalogError: string | null;
  mixedComponent: string | null;
  mixedTimeIndex: number;
  mixedTauIndex: number;
  mixedNambuStart: number;
  mixedNambuWindow: number;
  mixedSlice: MixedGreenFunctionSliceResponse | null;
  mixedSliceLoading: boolean;
  mixedSliceError: string | null;

  // Actions - Real-time
  setSelectedComponent: (component: string) => void;
  setRowIndex: (value: number) => void;
  setColIndex: (value: number) => void;
  setNambuStart: (value: number) => void;
  setNambuWindow: (value: number) => void;
  fetchCatalog: (runId: string) => Promise<void>;
  fetchSlice: (runId: string) => Promise<void>;

  // Actions - Thermal
  setThermalComponent: (component: string) => void;
  setTauIndex: (value: number) => void;
  setThermalNambuStart: (value: number) => void;
  setThermalNambuWindow: (value: number) => void;
  fetchThermalCatalog: (runId: string) => Promise<void>;
  fetchThermalSlice: (runId: string) => Promise<void>;

  // Actions - Mixed
  setMixedComponent: (component: string) => void;
  setMixedTimeIndex: (value: number) => void;
  setMixedTauIndex: (value: number) => void;
  setMixedNambuStart: (value: number) => void;
  setMixedNambuWindow: (value: number) => void;
  fetchMixedCatalog: (runId: string) => Promise<void>;
  fetchMixedSlice: (runId: string) => Promise<void>;

  // Reset
  resetAll: () => void;
};

const initialRealTime = {
  catalog: null,
  catalogLoading: false,
  catalogError: null,
  selectedComponent: null,
  rowIndex: 0,
  colIndex: 0,
  nambuStart: 0,
  nambuWindow: 4,
  slice: null,
  sliceLoading: false,
  sliceError: null,
};

const initialThermal = {
  thermalCatalog: null,
  thermalCatalogLoading: false,
  thermalCatalogError: null,
  thermalComponent: null,
  tauIndex: 0,
  thermalNambuStart: 0,
  thermalNambuWindow: 4,
  thermalSlice: null,
  thermalSliceLoading: false,
  thermalSliceError: null,
};

const initialMixed = {
  mixedCatalog: null,
  mixedCatalogLoading: false,
  mixedCatalogError: null,
  mixedComponent: null,
  mixedTimeIndex: 0,
  mixedTauIndex: 0,
  mixedNambuStart: 0,
  mixedNambuWindow: 4,
  mixedSlice: null,
  mixedSliceLoading: false,
  mixedSliceError: null,
};

export const useGreenFunctionStore = create<GreenFunctionState>()((set, get) => ({
  ...initialRealTime,
  ...initialThermal,
  ...initialMixed,

  // Real-time setters
  setSelectedComponent: (component) => set({ selectedComponent: component }),
  setRowIndex: (value) => set({ rowIndex: value }),
  setColIndex: (value) => set({ colIndex: value }),
  setNambuStart: (value) => set({ nambuStart: value }),
  setNambuWindow: (value) => set({ nambuWindow: value }),

  fetchCatalog: async (runId) => {
    set({ catalogLoading: true });
    try {
      const result = await listGreenFunctions(runId);
      const component = get().selectedComponent;
      set({
        catalog: result,
        catalogError: null,
        selectedComponent:
          component && result.components.includes(component)
            ? component
            : result.components[0] ?? null,
        rowIndex: Math.min(get().rowIndex, Math.max(result.time_point_count - 1, 0)),
        colIndex: Math.min(get().colIndex, Math.max(result.time_point_count - 1, 0)),
        nambuStart: Math.min(get().nambuStart, Math.max(result.nambu_dimension - 1, 0)),
        nambuWindow: clamp(get().nambuWindow, 1, Math.max(result.nambu_dimension, 1)),
      });
    } catch (error) {
      set({ catalog: null, catalogError: toErrorMessage(error) });
    } finally {
      set({ catalogLoading: false });
    }
  },

  fetchSlice: async (runId) => {
    const { catalog, selectedComponent, rowIndex, colIndex, nambuStart, nambuWindow } = get();
    if (!catalog || !selectedComponent) {
      set({ slice: null, sliceError: null });
      return;
    }

    const rowStop = clamp(rowIndex + 1, 1, catalog.time_point_count);
    const colStop = clamp(colIndex + 1, 1, catalog.time_point_count);
    const nambuStop = clamp(nambuStart + nambuWindow, 1, catalog.nambu_dimension);

    set({ sliceLoading: true });
    try {
      const result = await getGreenFunctionSlice(runId, selectedComponent, {
        row_start: Math.min(rowIndex, rowStop - 1),
        row_stop: rowStop,
        col_start: Math.min(colIndex, colStop - 1),
        col_stop: colStop,
        nambu_start: Math.min(nambuStart, nambuStop - 1),
        nambu_stop: nambuStop,
      });
      set({ slice: result, sliceError: null });
    } catch (error) {
      set({ slice: null, sliceError: toErrorMessage(error) });
    } finally {
      set({ sliceLoading: false });
    }
  },

  // Thermal setters
  setThermalComponent: (component) => set({ thermalComponent: component }),
  setTauIndex: (value) => set({ tauIndex: value }),
  setThermalNambuStart: (value) => set({ thermalNambuStart: value }),
  setThermalNambuWindow: (value) => set({ thermalNambuWindow: value }),

  fetchThermalCatalog: async (runId) => {
    set({ thermalCatalogLoading: true });
    try {
      const result = await listThermalBranch(runId);
      const component = get().thermalComponent;
      set({
        thermalCatalog: result,
        thermalCatalogError: null,
        thermalComponent:
          component && result.components.includes(component)
            ? component
            : result.components[0] ?? null,
        tauIndex: Math.min(get().tauIndex, Math.max(result.tau_point_count - 1, 0)),
        thermalNambuStart: Math.min(get().thermalNambuStart, Math.max(result.nambu_dimension - 1, 0)),
        thermalNambuWindow: clamp(get().thermalNambuWindow, 1, Math.max(result.nambu_dimension, 1)),
      });
    } catch (error) {
      set({ thermalCatalog: null, thermalCatalogError: toErrorMessage(error) });
    } finally {
      set({ thermalCatalogLoading: false });
    }
  },

  fetchThermalSlice: async (runId) => {
    const { thermalCatalog, thermalComponent, tauIndex, thermalNambuStart, thermalNambuWindow } = get();
    if (!thermalCatalog || !thermalComponent) {
      set({ thermalSlice: null, thermalSliceError: null });
      return;
    }

    const tauStop = clamp(tauIndex + 1, 1, thermalCatalog.tau_point_count);
    const nambuStop = clamp(thermalNambuStart + thermalNambuWindow, 1, thermalCatalog.nambu_dimension);

    set({ thermalSliceLoading: true });
    try {
      const result = await getThermalBranchSlice(runId, thermalComponent, {
        tau_start: Math.min(tauIndex, tauStop - 1),
        tau_stop: tauStop,
        nambu_start: Math.min(thermalNambuStart, nambuStop - 1),
        nambu_stop: nambuStop,
      });
      set({ thermalSlice: result, thermalSliceError: null });
    } catch (error) {
      set({ thermalSlice: null, thermalSliceError: toErrorMessage(error) });
    } finally {
      set({ thermalSliceLoading: false });
    }
  },

  // Mixed setters
  setMixedComponent: (component) => set({ mixedComponent: component }),
  setMixedTimeIndex: (value) => set({ mixedTimeIndex: value }),
  setMixedTauIndex: (value) => set({ mixedTauIndex: value }),
  setMixedNambuStart: (value) => set({ mixedNambuStart: value }),
  setMixedNambuWindow: (value) => set({ mixedNambuWindow: value }),

  fetchMixedCatalog: async (runId) => {
    set({ mixedCatalogLoading: true });
    try {
      const result = await listMixedGreenFunctions(runId);
      const component = get().mixedComponent;
      set({
        mixedCatalog: result,
        mixedCatalogError: null,
        mixedComponent:
          component && result.components.includes(component)
            ? component
            : result.components[0] ?? null,
        mixedTimeIndex: Math.min(get().mixedTimeIndex, Math.max(result.time_point_count - 1, 0)),
        mixedTauIndex: Math.min(get().mixedTauIndex, Math.max(result.tau_point_count - 1, 0)),
        mixedNambuStart: Math.min(get().mixedNambuStart, Math.max(result.nambu_dimension - 1, 0)),
        mixedNambuWindow: clamp(get().mixedNambuWindow, 1, Math.max(result.nambu_dimension, 1)),
      });
    } catch (error) {
      set({ mixedCatalog: null, mixedCatalogError: toErrorMessage(error) });
    } finally {
      set({ mixedCatalogLoading: false });
    }
  },

  fetchMixedSlice: async (runId) => {
    const { mixedCatalog, mixedComponent, mixedTimeIndex, mixedTauIndex, mixedNambuStart, mixedNambuWindow } = get();
    if (!mixedCatalog || !mixedComponent) {
      set({ mixedSlice: null, mixedSliceError: null });
      return;
    }

    const timeStop = clamp(mixedTimeIndex + 1, 1, mixedCatalog.time_point_count);
    const tauStop = clamp(mixedTauIndex + 1, 1, mixedCatalog.tau_point_count);
    const nambuStop = clamp(mixedNambuStart + mixedNambuWindow, 1, mixedCatalog.nambu_dimension);

    set({ mixedSliceLoading: true });
    try {
      const result = await getMixedGreenFunctionSlice(runId, mixedComponent, {
        time_start: Math.min(mixedTimeIndex, timeStop - 1),
        time_stop: timeStop,
        tau_start: Math.min(mixedTauIndex, tauStop - 1),
        tau_stop: tauStop,
        nambu_start: Math.min(mixedNambuStart, nambuStop - 1),
        nambu_stop: nambuStop,
      });
      set({ mixedSlice: result, mixedSliceError: null });
    } catch (error) {
      set({ mixedSlice: null, mixedSliceError: toErrorMessage(error) });
    } finally {
      set({ mixedSliceLoading: false });
    }
  },

  resetAll: () => set({ ...initialRealTime, ...initialThermal, ...initialMixed }),
}));
