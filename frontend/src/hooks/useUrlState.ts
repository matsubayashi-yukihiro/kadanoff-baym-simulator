import { useEffect } from "react";

import type { WorkbenchTab } from "../lib/workbench";

const DEFAULT_TAB: WorkbenchTab = "single-job";
const TAB_PATHS: Record<WorkbenchTab, string> = {
  "single-job": "/",
  "compare-jobs": "/compare-jobs",
  "parameter-sweep": "/parameter-sweep",
};

export type UrlState = {
  tab?: WorkbenchTab;
  runId?: string | null;
  observable?: string | null;
  component?: string | null;
  presetName?: string | null;
};

export function readUrlState(): UrlState {
  if (typeof window === "undefined") {
    return {};
  }

  const params = new URLSearchParams(window.location.search);
  const tab = parseWorkbenchPath(window.location.pathname) ?? parseWorkbenchTab(params.get("tab"));

  return {
    tab,
    runId: params.get("run"),
    observable: params.get("observable"),
    component: params.get("component"),
    presetName: params.get("preset"),
  };
}

export function useUrlStateSync(state: UrlState): void {
  useEffect(() => {
    writeUrlState(state);
  }, [state.tab, state.runId, state.observable, state.component, state.presetName]);
}

function writeUrlState(state: UrlState) {
  if (typeof window === "undefined") {
    return;
  }

  const params = new URLSearchParams(window.location.search);
  params.delete("tab");
  setQueryParam(params, "run", state.runId ?? null);
  setQueryParam(params, "observable", state.observable ?? null);
  setQueryParam(params, "component", state.component ?? null);
  setQueryParam(params, "preset", state.presetName ?? null);

  const search = params.toString();
  const nextPath = TAB_PATHS[state.tab ?? DEFAULT_TAB] ?? TAB_PATHS[DEFAULT_TAB];
  const nextUrl = `${nextPath}${search ? `?${search}` : ""}`;
  window.history.replaceState(null, "", nextUrl);
}

function setQueryParam(params: URLSearchParams, key: string, value: string | null | undefined) {
  if (!value) {
    params.delete(key);
    return;
  }
  params.set(key, value);
}

function parseWorkbenchTab(value: string | null): WorkbenchTab | undefined {
  if (value === "single-job" || value === "compare-jobs" || value === "parameter-sweep") {
    return value;
  }
  return undefined;
}

function parseWorkbenchPath(pathname: string): WorkbenchTab | undefined {
  const normalized = pathname.replace(/\/+$/, "") || "/";

  if (normalized === "/") {
    return "single-job";
  }
  if (normalized === "/compare-jobs") {
    return "compare-jobs";
  }
  if (normalized === "/parameter-sweep") {
    return "parameter-sweep";
  }

  return undefined;
}
