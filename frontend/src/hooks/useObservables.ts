import { useCallback, useEffect, useRef, useState } from "react";

import { getObservable, listObservables } from "../api/client";
import type { ObservableCatalogResponse, ObservableResponse, RunDetail } from "../api/types";
import { toErrorMessage } from "../lib/helpers";

export type UseObservablesReturn = {
  catalog: ObservableCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedObservable: string | null;
  setSelectedObservable: (name: string) => void;
  overlayNames: ReadonlySet<string>;
  toggleOverlay: (name: string) => void;
  data: ObservableResponse | null;
  dataLoading: boolean;
  dataError: string | null;
  overlayData: ReadonlyMap<string, ObservableResponse>;
};

export function useObservables(
  selectedRunId: string | null,
  selectedRun: RunDetail | null,
  initialObservable: string | null,
): UseObservablesReturn {
  const [catalog, setCatalog] = useState<ObservableCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedObservable, setSelectedObservable] = useState<string | null>(initialObservable);
  const [data, setData] = useState<ObservableResponse | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [overlayNames, setOverlayNames] = useState<Set<string>>(new Set());
  const [overlayData, setOverlayData] = useState<Map<string, ObservableResponse>>(new Map());
  const overlayAbortRef = useRef<Map<string, AbortController>>(new Map());

  const toggleOverlay = useCallback((name: string) => {
    setOverlayNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
        setOverlayData((prevData) => {
          const nextData = new Map(prevData);
          nextData.delete(name);
          return nextData;
        });
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (!selectedRunId || selectedRun?.state !== "succeeded") {
      setCatalog(null);
      setCatalogError(null);
      setCatalogLoading(false);
      return;
    }

    let active = true;
    setCatalogLoading(true);

    listObservables(selectedRunId)
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
  }, [selectedRunId, selectedRun?.state]);

  // Reset overlay when run changes
  useEffect(() => {
    setOverlayNames(new Set());
    setOverlayData(new Map());
  }, [selectedRunId]);

  useEffect(() => {
    const names = catalog?.observables ?? [];
    if (names.length === 0) {
      setSelectedObservable(null);
      return;
    }

    if (!selectedObservable || !names.includes(selectedObservable)) {
      setSelectedObservable(names[0]);
    }
  }, [catalog, selectedObservable]);

  useEffect(() => {
    if (!selectedRunId || !selectedObservable || selectedRun?.state !== "succeeded") {
      setData(null);
      setDataError(null);
      setDataLoading(false);
      return;
    }

    let active = true;
    setDataLoading(true);

    getObservable(selectedRunId, selectedObservable)
      .then((result) => {
        if (!active) return;
        setData(result);
        setDataError(null);
      })
      .catch((error) => {
        if (!active) return;
        setData(null);
        setDataError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) setDataLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, selectedObservable, selectedRun?.state]);

  // Fetch overlay data for each overlayName not yet in overlayData
  useEffect(() => {
    if (!selectedRunId || selectedRun?.state !== "succeeded") return;

    for (const name of overlayNames) {
      if (name === selectedObservable) continue;
      if (overlayData.has(name)) continue;
      if (overlayAbortRef.current.has(name)) continue;

      const controller = new AbortController();
      overlayAbortRef.current.set(name, controller);

      getObservable(selectedRunId, name)
        .then((result) => {
          if (!controller.signal.aborted) {
            setOverlayData((prev) => new Map(prev).set(name, result));
          }
        })
        .catch(() => {
          // silently ignore overlay fetch failures
        })
        .finally(() => {
          overlayAbortRef.current.delete(name);
        });
    }
  }, [selectedRunId, selectedRun?.state, selectedObservable, overlayNames, overlayData]);

  return {
    catalog,
    catalogLoading,
    catalogError,
    selectedObservable,
    setSelectedObservable,
    overlayNames,
    toggleOverlay,
    data,
    dataLoading,
    dataError,
    overlayData,
  };
}
