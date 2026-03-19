import { useEffect, useState } from "react";

import { getMixedGreenFunctionSlice, listMixedGreenFunctions } from "../api/client";
import type { MixedGreenFunctionCatalogResponse, MixedGreenFunctionSliceResponse, RunDetail } from "../api/types";
import { clamp, toErrorMessage } from "../lib/helpers";

export type UseMixedGreenFunctionsReturn = {
  catalog: MixedGreenFunctionCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedComponent: string | null;
  setSelectedComponent: (component: string) => void;
  timeIndex: number;
  tauIndex: number;
  nambuStart: number;
  nambuWindow: number;
  setTimeIndex: (value: number) => void;
  setTauIndex: (value: number) => void;
  setNambuStart: (value: number) => void;
  setNambuWindow: (value: number) => void;
  slice: MixedGreenFunctionSliceResponse | null;
  sliceLoading: boolean;
  sliceError: string | null;
};

export function useMixedGreenFunctions(
  selectedRunId: string | null,
  selectedRun: RunDetail | null,
): UseMixedGreenFunctionsReturn {
  const [catalog, setCatalog] = useState<MixedGreenFunctionCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null);
  const [slice, setSlice] = useState<MixedGreenFunctionSliceResponse | null>(null);
  const [sliceLoading, setSliceLoading] = useState(false);
  const [sliceError, setSliceError] = useState<string | null>(null);
  const [timeIndex, setTimeIndex] = useState(0);
  const [tauIndex, setTauIndex] = useState(0);
  const [nambuStart, setNambuStart] = useState(0);
  const [nambuWindow, setNambuWindow] = useState(4);

  const shouldLoad =
    Boolean(selectedRunId) &&
    selectedRun?.state === "succeeded" &&
    selectedRun?.solver === "kbe_hfb" &&
    selectedRun?.config?.thermal_branch?.enabled === true;

  useEffect(() => {
    if (!shouldLoad || !selectedRunId) {
      setCatalog(null);
      setCatalogError(null);
      setCatalogLoading(false);
      setSelectedComponent(null);
      setSlice(null);
      setSliceError(null);
      return;
    }

    let active = true;
    setCatalogLoading(true);

    listMixedGreenFunctions(selectedRunId)
      .then((result) => {
        if (!active) return;
        setCatalog(result);
        setCatalogError(null);
      })
      .catch((error) => {
        if (!active) return;
        setCatalog(null);
        setCatalogError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) setCatalogLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, shouldLoad]);

  useEffect(() => {
    if (!catalog) {
      setSelectedComponent(null);
      setTimeIndex(0);
      setTauIndex(0);
      setNambuStart(0);
      setNambuWindow(4);
      return;
    }

    const maxTimeIndex = Math.max(catalog.time_point_count - 1, 0);
    const maxTauIndex = Math.max(catalog.tau_point_count - 1, 0);
    const maxNambuStart = Math.max(catalog.nambu_dimension - 1, 0);

    if (!selectedComponent || !catalog.components.includes(selectedComponent)) {
      setSelectedComponent(catalog.components[0] ?? null);
    }

    setTimeIndex((current) => Math.min(current, maxTimeIndex));
    setTauIndex((current) => Math.min(current, maxTauIndex));
    setNambuStart((current) => Math.min(current, maxNambuStart));
    setNambuWindow((current) => clamp(current, 1, Math.max(catalog.nambu_dimension, 1)));
  }, [catalog, selectedComponent]);

  useEffect(() => {
    if (!selectedRunId || !catalog || !selectedComponent) {
      setSlice(null);
      setSliceError(null);
      setSliceLoading(false);
      return;
    }

    const timeStop = clamp(timeIndex + 1, 1, catalog.time_point_count);
    const tauStop = clamp(tauIndex + 1, 1, catalog.tau_point_count);
    const nambuStop = clamp(nambuStart + nambuWindow, 1, catalog.nambu_dimension);

    let active = true;
    setSliceLoading(true);

    getMixedGreenFunctionSlice(selectedRunId, selectedComponent, {
      time_start: Math.min(timeIndex, timeStop - 1),
      time_stop: timeStop,
      tau_start: Math.min(tauIndex, tauStop - 1),
      tau_stop: tauStop,
      nambu_start: Math.min(nambuStart, nambuStop - 1),
      nambu_stop: nambuStop,
    })
      .then((result) => {
        if (!active) return;
        setSlice(result);
        setSliceError(null);
      })
      .catch((error) => {
        if (!active) return;
        setSlice(null);
        setSliceError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) setSliceLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, catalog, selectedComponent, timeIndex, tauIndex, nambuStart, nambuWindow]);

  return {
    catalog,
    catalogLoading,
    catalogError,
    selectedComponent,
    setSelectedComponent,
    timeIndex,
    tauIndex,
    nambuStart,
    nambuWindow,
    setTimeIndex,
    setTauIndex,
    setNambuStart,
    setNambuWindow,
    slice,
    sliceLoading,
    sliceError,
  };
}
