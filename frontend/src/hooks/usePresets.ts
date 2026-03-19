import { useEffect, useState } from "react";

import { listPresets } from "../api/client";
import type { PresetEntry } from "../api/types";
import { toErrorMessage } from "../lib/helpers";
import { createFallbackPresets } from "../lib/workbench";

export type UsePresetsReturn = {
  presets: PresetEntry[];
  presetsLoading: boolean;
  presetError: string | null;
};

export function usePresets(): UsePresetsReturn {
  const [presets, setPresets] = useState<PresetEntry[]>(() => createFallbackPresets());
  const [presetsLoading, setPresetsLoading] = useState(true);
  const [presetError, setPresetError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setPresetsLoading(true);

    listPresets()
      .then((items) => {
        if (!active) return;
        setPresets(items);
        setPresetError(null);
      })
      .catch((error) => {
        if (!active) return;
        setPresets(createFallbackPresets());
        setPresetError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) setPresetsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return { presets, presetsLoading, presetError };
}
