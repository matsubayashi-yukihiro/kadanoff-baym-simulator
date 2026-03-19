import { useEffect, useState } from "react";

import { getGreenFunctionSlice, listGreenFunctions } from "../api/client";
import type { GreenFunctionCatalogResponse, GreenFunctionSliceResponse, RunDetail } from "../api/types";
import { clamp, toErrorMessage } from "../lib/helpers";

export type UseGreenFunctionsReturn = {
  catalog: GreenFunctionCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedComponent: string | null;
  setSelectedComponent: (component: string) => void;
  rowIndex: number;
  colIndex: number;
  nambuStart: number;
  nambuWindow: number;
  setRowIndex: (value: number) => void;
  setColIndex: (value: number) => void;
  setNambuStart: (value: number) => void;
  setNambuWindow: (value: number) => void;
  slice: GreenFunctionSliceResponse | null;
  sliceLoading: boolean;
  sliceError: string | null;
};

export function useGreenFunctions(
  selectedRunId: string | null,
  selectedRun: RunDetail | null,
  initialComponent: string | null,
): UseGreenFunctionsReturn {
  const [catalog, setCatalog] = useState<GreenFunctionCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<string | null>(initialComponent);
  const [slice, setSlice] = useState<GreenFunctionSliceResponse | null>(null);
  const [sliceLoading, setSliceLoading] = useState(false);
  const [sliceError, setSliceError] = useState<string | null>(null);
  const [rowIndex, setRowIndex] = useState(0);
  const [colIndex, setColIndex] = useState(0);
  const [nambuStart, setNambuStart] = useState(0);
  const [nambuWindow, setNambuWindow] = useState(4);

  useEffect(() => {
    const shouldLoad =
      Boolean(selectedRunId) && selectedRun?.state === "succeeded" && selectedRun?.solver === "kbe_hfb";

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

    listGreenFunctions(selectedRunId)
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
  }, [selectedRunId, selectedRun?.solver, selectedRun?.state]);

  useEffect(() => {
    if (!catalog) {
      setSelectedComponent(null);
      setRowIndex(0);
      setColIndex(0);
      setNambuStart(0);
      setNambuWindow(4);
      return;
    }

    const maxTimeIndex = Math.max(catalog.time_point_count - 1, 0);
    const maxNambuStart = Math.max(catalog.nambu_dimension - 1, 0);

    if (!selectedComponent || !catalog.components.includes(selectedComponent)) {
      setSelectedComponent(catalog.components[0] ?? null);
    }

    setRowIndex((current) => Math.min(current, maxTimeIndex));
    setColIndex((current) => Math.min(current, maxTimeIndex));
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

    const rowStop = clamp(rowIndex + 1, 1, catalog.time_point_count);
    const colStop = clamp(colIndex + 1, 1, catalog.time_point_count);
    const nambuStop = clamp(nambuStart + nambuWindow, 1, catalog.nambu_dimension);

    let active = true;
    setSliceLoading(true);

    getGreenFunctionSlice(selectedRunId, selectedComponent, {
      row_start: Math.min(rowIndex, rowStop - 1),
      row_stop: rowStop,
      col_start: Math.min(colIndex, colStop - 1),
      col_stop: colStop,
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
  }, [selectedRunId, catalog, selectedComponent, rowIndex, colIndex, nambuStart, nambuWindow]);

  return {
    catalog,
    catalogLoading,
    catalogError,
    selectedComponent,
    setSelectedComponent,
    rowIndex,
    colIndex,
    nambuStart,
    nambuWindow,
    setRowIndex,
    setColIndex,
    setNambuStart,
    setNambuWindow,
    slice,
    sliceLoading,
    sliceError,
  };
}
