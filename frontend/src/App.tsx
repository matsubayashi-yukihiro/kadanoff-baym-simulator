import { startTransition, useEffect, useState } from "react";

import { createRun, getObservable, getRun, listObservables, listRuns } from "./api/client";
import type { ObservableCatalogResponse, ObservableResponse, RunDetail, RunSummary, SimulationConfigInput } from "./api/types";
import { ConfigPanel } from "./components/ConfigPanel";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { ObservablePanel } from "./components/ObservablePanel";
import { RunControlPanel } from "./components/RunControlPanel";
import { createDefaultConfig } from "./lib/defaultConfig";

const POLL_INTERVAL_MS = 1500;

export default function App() {
  const [config, setConfig] = useState<SimulationConfigInput>(() => createDefaultConfig());
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runsVersion, setRunsVersion] = useState(0);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runVersion, setRunVersion] = useState(0);

  const [catalog, setCatalog] = useState<ObservableCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedObservable, setSelectedObservable] = useState<string | null>(null);
  const [observableData, setObservableData] = useState<ObservableResponse | null>(null);
  const [observableLoading, setObservableLoading] = useState(false);
  const [observableError, setObservableError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setRunsLoading(true);
    setRunsError(null);

    listRuns()
      .then((payload) => {
        if (!active) {
          return;
        }
        setRuns(payload);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setRunsError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) {
          setRunsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [runsVersion]);

  useEffect(() => {
    if (runs.length === 0) {
      setSelectedRunId(null);
      return;
    }

    if (!selectedRunId || !runs.some((run) => run.run_id === selectedRunId)) {
      setSelectedRunId(runs[0].run_id);
    }
  }, [runs, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      setRunError(null);
      return;
    }

    let active = true;
    setRunLoading(true);
    setRunError(null);

    getRun(selectedRunId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setSelectedRun(payload);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setSelectedRun(null);
        setRunError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) {
          setRunLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, runVersion]);

  useEffect(() => {
    if (!selectedRunId || !selectedRun || selectedRun.state !== "succeeded") {
      setCatalog(null);
      setCatalogError(null);
      setCatalogLoading(false);
      return;
    }

    let active = true;
    setCatalogLoading(true);
    setCatalogError(null);

    listObservables(selectedRunId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setCatalog(payload);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setCatalog(null);
        setCatalogError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) {
          setCatalogLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, selectedRun?.state, selectedRun?.updated_at]);

  useEffect(() => {
    if (!catalog || catalog.observables.length === 0) {
      setSelectedObservable(null);
      return;
    }

    setSelectedObservable((current) => {
      if (current && catalog.observables.includes(current)) {
        return current;
      }
      if (catalog.observables.includes("density")) {
        return "density";
      }
      return catalog.observables[0];
    });
  }, [catalog]);

  useEffect(() => {
    if (!selectedRunId || !selectedObservable || selectedRun?.state !== "succeeded") {
      setObservableData(null);
      setObservableError(null);
      setObservableLoading(false);
      return;
    }

    let active = true;
    setObservableLoading(true);
    setObservableError(null);

    getObservable(selectedRunId, selectedObservable)
      .then((payload) => {
        if (!active) {
          return;
        }
        setObservableData(payload);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setObservableData(null);
        setObservableError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) {
          setObservableLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedRunId, selectedObservable, selectedRun?.state]);

  useEffect(() => {
    if (!selectedRunId || !selectedRun || isTerminalState(selectedRun.state)) {
      return;
    }

    const timer = window.setInterval(() => {
      setRunVersion((current) => current + 1);
      setRunsVersion((current) => current + 1);
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [selectedRunId, selectedRun]);

  async function handleCreateRun() {
    setSubmitting(true);
    setSubmitError(null);

    try {
      const created = await createRun(config);
      setSelectedRun(created);
      setCatalog(null);
      setObservableData(null);
      startTransition(() => {
        setSelectedRunId(created.run_id);
      });
      setRunsVersion((current) => current + 1);
      setRunVersion((current) => current + 1);
    } catch (error) {
      setSubmitError(toErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  function handleRefresh() {
    setRunsVersion((current) => current + 1);
    setRunVersion((current) => current + 1);
  }

  function handleSelectRun(runId: string) {
    setCatalog(null);
    setObservableData(null);
    setObservableError(null);
    startTransition(() => {
      setSelectedRunId(runId);
    });
  }

  function handleSelectObservable(name: string) {
    startTransition(() => {
      setSelectedObservable(name);
    });
  }

  return (
    <main className="app-shell">
      <div className="app-backdrop" />
      <section className="hero">
        <p className="hero-kicker">TDKB Minimal Research UI</p>
        <h1>FastAPI-backed lab console for solver runs and observable traces.</h1>
        <p className="hero-copy">
          This frontend targets the currently implemented noninteracting backend path and keeps the run loop visible end to end:
          config edit, submission, polling, diagnostics, and time-series inspection.
        </p>
      </section>

      <div className="layout-grid">
        <ConfigPanel
          config={config}
          disabled={submitting}
          onConfigChange={setConfig}
          onReset={() => setConfig(createDefaultConfig())}
        />
        <RunControlPanel
          isSubmitting={submitting}
          runs={runs}
          runsLoading={runsLoading}
          runsError={runsError}
          runLoading={runLoading}
          runError={runError}
          submitError={submitError}
          selectedRun={selectedRun}
          selectedRunId={selectedRunId}
          onCreateRun={handleCreateRun}
          onRefresh={handleRefresh}
          onSelectRun={handleSelectRun}
        />
        <ObservablePanel
          catalog={catalog}
          catalogLoading={catalogLoading}
          catalogError={catalogError}
          data={observableData}
          dataLoading={observableLoading}
          dataError={observableError}
          run={selectedRun}
          selectedObservable={selectedObservable}
          onSelectObservable={handleSelectObservable}
        />
        <DiagnosticsPanel run={selectedRun} />
      </div>
    </main>
  );
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

function isTerminalState(state: RunDetail["state"]): boolean {
  return state === "succeeded" || state === "failed" || state === "cancelled";
}
