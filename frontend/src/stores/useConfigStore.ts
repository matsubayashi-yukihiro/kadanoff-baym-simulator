import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { PresetEntry, SimulationConfigInput } from "../api/types";
import { listPresets } from "../api/client";
import { createDefaultConfig } from "../lib/defaultConfig";
import { cloneConfig, createFallbackPresets, sanitizeSimulationConfig } from "../lib/workbench";
import { toErrorMessage } from "../lib/helpers";

type ConfigState = {
  draftConfig: SimulationConfigInput;
  loadedPresetName: string | null;
  presets: PresetEntry[];
  presetsLoading: boolean;
  presetError: string | null;

  setDraftConfig: (config: SimulationConfigInput) => void;
  loadPreset: (preset: PresetEntry) => void;
  resetDraft: () => void;
  setLoadedPresetName: (name: string | null) => void;
  fetchPresets: () => Promise<void>;
};

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      draftConfig: createDefaultConfig(),
      loadedPresetName: null,
      presets: createFallbackPresets(),
      presetsLoading: false,
      presetError: null,

      setDraftConfig: (config) => set({ draftConfig: sanitizeSimulationConfig(config) }),

      loadPreset: (preset) =>
        set({
          draftConfig: cloneConfig(preset),
          loadedPresetName: preset.name ?? null,
        }),

      resetDraft: () =>
        set({
          draftConfig: createDefaultConfig(),
          loadedPresetName: null,
        }),

      setLoadedPresetName: (name) => set({ loadedPresetName: name }),

      fetchPresets: async () => {
        set({ presetsLoading: true });
        try {
          const result = await listPresets();
          set({ presets: result, presetError: null });
        } catch (error) {
          set({
            presets: createFallbackPresets(),
            presetError: toErrorMessage(error),
          });
        } finally {
          set({ presetsLoading: false });
        }
      },
    }),
    {
      name: "tdkb-config-storage",
      merge: (persistedState, currentState) => {
        const persisted = (persistedState ?? {}) as Partial<ConfigState>;
        return {
          ...currentState,
          ...persisted,
          draftConfig: sanitizeSimulationConfig(persisted.draftConfig ?? currentState.draftConfig),
          loadedPresetName: persisted.loadedPresetName ?? currentState.loadedPresetName,
        };
      },
      partialize: (state) => ({
        draftConfig: state.draftConfig,
        loadedPresetName: state.loadedPresetName,
      }),
    }
  )
);
