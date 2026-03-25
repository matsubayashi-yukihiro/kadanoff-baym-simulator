import { useEffect, useState } from "react";

import { getThermalBranchSlice, listThermalBranch } from "../api/client";
import type { RunDetail, ThermalBranchCatalogResponse, ThermalBranchSliceResponse } from "../api/types";
import { clamp, isSuccessfulState, toErrorMessage } from "../lib/helpers";

export type UseThermalBranchReturn = {
  catalog: ThermalBranchCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedComponent: string | null;
  setSelectedComponent: (component: string) => void;
  tauIndex: number;
  nambuStart: number;
  nambuWindow: number;
  setTauIndex: (value: number) => void;
  setNambuStart: (value: number) => void;
  setNambuWindow: (value: number) => void;
  slice: ThermalBranchSliceResponse | null;
  sliceLoading: boolean;
  sliceError: string | null;
};

export function useThermalBranch(
  selectedRunId: string | null,
  selectedRun: RunDetail | null,
): UseThermalBranchReturn {
  const [catalog, setCatalog] = useState<ThermalBranchCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null);
  const [slice, setSlice] = useState<ThermalBranchSliceResponse | null>(null);
  const [sliceLoading, setSliceLoading] = useState(false);
  const [sliceError, setSliceError] = useState<string | null>(null);
  const [tauIndex, setTauIndex] = useState(0);
  const [nambuStart, setNambuStart] = useState(0);
  const [nambuWindow, setNambuWindow] = useState(4);

  const shouldLoad =
    Boolean(selectedRunId) &&
    Boolean(selectedRun && isSuccessfulState(selectedRun.state)) &&
    selectedRun?.solver === "kbe_hfb" &&
    selectedRun?.config?.representation !== "k_space" &&
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

    listThermalBranch(selectedRunId)
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
      setTauIndex(0);
      setNambuStart(0);
      setNambuWindow(4);
      return;
    }

    const maxTauIndex = Math.max(catalog.tau_point_count - 1, 0);
    const maxNambuStart = Math.max(catalog.nambu_dimension - 1, 0);

    if (!selectedComponent || !catalog.components.includes(selectedComponent)) {
      setSelectedComponent(catalog.components[0] ?? null);
    }

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

    const tauStop = clamp(tauIndex + 1, 1, catalog.tau_point_count);
    const nambuStop = clamp(nambuStart + nambuWindow, 1, catalog.nambu_dimension);

    let active = true;
    setSliceLoading(true);

    getThermalBranchSlice(selectedRunId, selectedComponent, {
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
  }, [selectedRunId, catalog, selectedComponent, tauIndex, nambuStart, nambuWindow]);

  return {
    catalog,
    catalogLoading,
    catalogError,
    selectedComponent,
    setSelectedComponent,
    tauIndex,
    nambuStart,
    nambuWindow,
    setTauIndex,
    setNambuStart,
    setNambuWindow,
    slice,
    sliceLoading,
    sliceError,
  };
}
