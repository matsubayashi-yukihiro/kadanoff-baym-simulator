import { startTransition, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createRun,
  getGreenFunctionSlice,
  getObservable,
  getRun,
  listGreenFunctions,
} from "./api/client";
import type {
  GreenFunctionCatalogResponse,
  GreenFunctionSliceResponse,
  ObservableResponse,
  RunDetail,
  SimulationConfigInput,
} from "./api/types";
import { ConfigPanel } from "./components/ConfigPanel";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { GreenFunctionPanel } from "./components/GreenFunctionPanel";
import { JobSummaryTable } from "./components/JobSummaryTable";
import { JobTabsBar } from "./components/JobTabsBar";
import { JobWorkbenchPanel } from "./components/JobWorkbenchPanel";
import {
  ObservableComparePanel,
  type ComparePlotSelection,
} from "./components/ObservableComparePanel";
import {
  applyJobColumnValue,
  computeVisibleParameterColumns,
  createWorkspaceJob,
  isTerminalRunState,
  renameJob,
  restoreWorkspaceSnapshot,
  snapshotWorkspace,
  type JobColumn,
  type WorkspaceJob,
} from "./lib/workspace";
import { createDefaultConfig, SUPPORTED_OBSERVABLES } from "./lib/defaultConfig";

const POLL_INTERVAL_MS = 1500;
const WORKSPACE_STORAGE_KEY = "tdkb.workspace.v2";

type CompareObservableRequest = {
  cacheKey: string;
  runId: string;
  observable: string;
};

export default function App() {
  const [jobs, setJobs] = useState<WorkspaceJob[]>(() => {
    const snapshot =
      typeof window !== "undefined" ? restoreWorkspaceSnapshot(window.localStorage.getItem(WORKSPACE_STORAGE_KEY)) : null;
    return snapshot?.jobs ?? [createWorkspaceJob([])];
  });
  const [activeJobId, setActiveJobId] = useState<string | null>(() => {
    const snapshot =
      typeof window !== "undefined" ? restoreWorkspaceSnapshot(window.localStorage.getItem(WORKSPACE_STORAGE_KEY)) : null;
    return snapshot?.activeJobId ?? snapshot?.jobs[0]?.id ?? null;
  });
  const [showDifferentOnly, setShowDifferentOnly] = useState(false);

  const [runsById, setRunsById] = useState<Record<string, RunDetail>>({});
  const [runErrors, setRunErrors] = useState<Record<string, string>>({});
  const [runRefreshVersion, setRunRefreshVersion] = useState(0);

  const [submittingJobId, setSubmittingJobId] = useState<string | null>(null);
  const [submitErrors, setSubmitErrors] = useState<Record<string, string>>({});

  const [comparePlots, setComparePlots] = useState<ComparePlotSelection[]>([]);
  const [compareDataByKey, setCompareDataByKey] = useState<Record<string, ObservableResponse>>({});
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  const [greenCatalog, setGreenCatalog] = useState<GreenFunctionCatalogResponse | null>(null);
  const [greenCatalogLoading, setGreenCatalogLoading] = useState(false);
  const [greenCatalogError, setGreenCatalogError] = useState<string | null>(null);
  const [selectedGreenComponent, setSelectedGreenComponent] = useState<string | null>(null);
  const [greenSlice, setGreenSlice] = useState<GreenFunctionSliceResponse | null>(null);
  const [greenSliceLoading, setGreenSliceLoading] = useState(false);
  const [greenSliceError, setGreenSliceError] = useState<string | null>(null);
  const [greenRowIndex, setGreenRowIndex] = useState(0);
  const [greenColIndex, setGreenColIndex] = useState(0);
  const [greenNambuStart, setGreenNambuStart] = useState(0);
  const [greenNambuWindow, setGreenNambuWindow] = useState(4);

  const activeJob = jobs.find((job) => job.id === activeJobId) ?? jobs[0] ?? null;
  const activeRun = activeJob?.lastRunId ? runsById[activeJob.lastRunId] ?? null : null;
  const activeRunError = activeJob?.lastRunId ? runErrors[activeJob.lastRunId] ?? null : null;
  const activeSubmitError = activeJob ? submitErrors[activeJob.id] ?? null : null;

  const trackedRunIds = useMemo(
    () => Array.from(new Set(jobs.flatMap((job) => job.runHistory))),
    [jobs],
  );

  const pendingRunIds = useMemo(
    () =>
      trackedRunIds.filter((runId) => {
        const run = runsById[runId];
        return !run || !isTerminalRunState(run.state);
      }),
    [trackedRunIds, runsById],
  );

  const compareJobs = useMemo(
    () =>
      jobs.filter((job) => {
        if (!job.plotEnabled || !job.lastRunId) {
          return false;
        }
        return runsById[job.lastRunId]?.state === "succeeded";
      }),
    [jobs, runsById],
  );

  const observableOptions = useMemo(() => {
    const options = new Set<string>();
    for (const job of compareJobs) {
      if (!job.lastRunId) {
        continue;
      }
      const run = runsById[job.lastRunId];
      for (const descriptor of run?.available_observables ?? []) {
        options.add(descriptor.name);
      }
    }
    return sortObservableNames(Array.from(options));
  }, [compareJobs, runsById]);

  const compareEntries = useMemo(
    () =>
      compareJobs
        .map((job) => {
          const runId = job.lastRunId;
          if (!runId) {
            return null;
          }
          return {
            jobId: job.id,
            jobTitle: job.title,
            runId,
          };
        })
        .filter((entry): entry is { jobId: string; jobTitle: string; runId: string } => entry !== null),
    [compareJobs],
  );

  const parameterColumns = useMemo(
    () => computeVisibleParameterColumns(jobs, showDifferentOnly, activeJobId),
    [jobs, showDifferentOnly, activeJobId],
  );

  const compareRequests = useMemo<CompareObservableRequest[]>(
    () =>
      compareEntries.flatMap((entry) =>
        comparePlots.flatMap((plot) => {
          if (!plot.observable) {
            return [];
          }

          return [
            {
              cacheKey: buildObservableCacheKey(entry.runId, plot.observable),
              runId: entry.runId,
              observable: plot.observable,
            },
          ];
        }),
      ),
    [compareEntries, comparePlots],
  );

  const missingCompareRequests = useMemo(
    () =>
      compareRequests.filter((request, index, allRequests) => {
        if (compareDataByKey[request.cacheKey]) {
          return false;
        }
        return allRequests.findIndex((candidate) => candidate.cacheKey === request.cacheKey) === index;
      }),
    [compareDataByKey, compareRequests],
  );

  useEffect(() => {
    if (jobs.length === 0) {
      const fallback = createWorkspaceJob([]);
      setJobs([fallback]);
      setActiveJobId(fallback.id);
      return;
    }

    if (!activeJobId || !jobs.some((job) => job.id === activeJobId)) {
      setActiveJobId(jobs[0].id);
    }
  }, [jobs, activeJobId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, snapshotWorkspace(jobs, activeJobId));
  }, [jobs, activeJobId]);

  useEffect(() => {
    if (trackedRunIds.length === 0) {
      return;
    }

    let active = true;

    Promise.all(
      trackedRunIds.map(async (runId) => {
        try {
          const run = await getRun(runId);
          return { runId, run };
        } catch (error) {
          return { runId, error: toErrorMessage(error) };
        }
      }),
    ).then((results) => {
      if (!active) {
        return;
      }

      setRunsById((current) => {
        const next = { ...current };
        for (const result of results) {
          if ("run" in result && result.run) {
            next[result.runId] = result.run;
          }
        }
        return next;
      });

      setRunErrors((current) => {
        const next = { ...current };
        for (const result of results) {
          if ("error" in result) {
            next[result.runId] = result.error ?? "Failed to load run";
          } else {
            delete next[result.runId];
          }
        }
        return next;
      });
    });

    return () => {
      active = false;
    };
  }, [trackedRunIds.join("|"), runRefreshVersion]);

  useEffect(() => {
    if (pendingRunIds.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      setRunRefreshVersion((current) => current + 1);
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [pendingRunIds.join("|")]);

  useEffect(() => {
    if (observableOptions.length === 0) {
      setComparePlots([]);
      setCompareLoading(false);
      setCompareError(null);
      return;
    }

    setComparePlots((current) => reconcileComparePlots(current, observableOptions));
  }, [observableOptions]);

  useEffect(() => {
    if (compareEntries.length === 0 || comparePlots.length === 0) {
      setCompareLoading(false);
      setCompareError(null);
      return;
    }

    if (missingCompareRequests.length === 0) {
      setCompareLoading(false);
      setCompareError(null);
      return;
    }

    let active = true;
    setCompareLoading(true);
    setCompareError(null);

    Promise.all(
      missingCompareRequests.map(async (request) => {
        try {
          const data = await getObservable(request.runId, request.observable);
          return { ...request, data };
        } catch (error) {
          return { ...request, error: toErrorMessage(error) };
        }
      }),
    )
      .then((results) => {
        if (!active) {
          return;
        }

        setCompareDataByKey((current) => {
          const next = { ...current };
          for (const result of results) {
            if ("data" in result && result.data) {
              next[result.cacheKey] = result.data;
            }
          }
          return next;
        });

        const errors = results
          .filter((result) => "error" in result)
          .map((result) => `${result.runId}:${result.observable}`);
        setCompareError(errors.length > 0 ? `Failed to load ${errors.join(" | ")}` : null);
      })
      .finally(() => {
        if (active) {
          setCompareLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [compareEntries, comparePlots.length, missingCompareRequests]);

  useEffect(() => {
    if (!activeRun || activeRun.state !== "succeeded" || activeRun.solver !== "kbe_hfb") {
      setGreenCatalog(null);
      setGreenCatalogError(null);
      setGreenCatalogLoading(false);
      return;
    }

    let active = true;
    setGreenCatalogLoading(true);
    setGreenCatalogError(null);

    listGreenFunctions(activeRun.run_id)
      .then((payload) => {
        if (!active) {
          return;
        }
        setGreenCatalog(payload);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        if (error instanceof ApiError && error.status === 404) {
          setGreenCatalog(null);
          setGreenCatalogError(null);
          return;
        }
        setGreenCatalog(null);
        setGreenCatalogError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) {
          setGreenCatalogLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [activeRun?.run_id, activeRun?.solver, activeRun?.state, activeRun?.updated_at]);

  useEffect(() => {
    if (!greenCatalog || greenCatalog.components.length === 0) {
      setSelectedGreenComponent(null);
      return;
    }

    setSelectedGreenComponent((current) => {
      if (current && greenCatalog.components.includes(current)) {
        return current;
      }
      if (greenCatalog.components.includes("retarded")) {
        return "retarded";
      }
      return greenCatalog.components[0];
    });

    const lastTimeIndex = Math.max(greenCatalog.time_point_count - 1, 0);
    setGreenRowIndex(lastTimeIndex);
    setGreenColIndex(lastTimeIndex);
    setGreenNambuStart(0);
    setGreenNambuWindow(Math.min(4, greenCatalog.nambu_dimension));
  }, [greenCatalog]);

  useEffect(() => {
    if (
      !activeRun ||
      !greenCatalog ||
      !selectedGreenComponent ||
      activeRun.state !== "succeeded" ||
      activeRun.solver !== "kbe_hfb"
    ) {
      setGreenSlice(null);
      setGreenSliceError(null);
      setGreenSliceLoading(false);
      return;
    }

    const rowStart = clampIndex(greenRowIndex, Math.max(greenCatalog.time_point_count - 1, 0));
    const colStart = clampIndex(greenColIndex, Math.max(greenCatalog.time_point_count - 1, 0));
    const nambuStart = clampIndex(greenNambuStart, Math.max(greenCatalog.nambu_dimension - 1, 0));
    const nambuStop = Math.min(greenCatalog.nambu_dimension, nambuStart + Math.max(1, greenNambuWindow));

    let active = true;
    setGreenSliceLoading(true);
    setGreenSliceError(null);

    getGreenFunctionSlice(activeRun.run_id, selectedGreenComponent, {
      row_start: rowStart,
      row_stop: rowStart + 1,
      col_start: colStart,
      col_stop: colStart + 1,
      nambu_start: nambuStart,
      nambu_stop: nambuStop,
    })
      .then((payload) => {
        if (!active) {
          return;
        }
        setGreenSlice(payload);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setGreenSlice(null);
        setGreenSliceError(toErrorMessage(error));
      })
      .finally(() => {
        if (active) {
          setGreenSliceLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [
    activeRun?.run_id,
    activeRun?.solver,
    activeRun?.state,
    greenCatalog,
    selectedGreenComponent,
    greenRowIndex,
    greenColIndex,
    greenNambuStart,
    greenNambuWindow,
  ]);

  function updateJob(jobId: string, updater: (job: WorkspaceJob) => WorkspaceJob) {
    setJobs((current) => current.map((job) => (job.id === jobId ? updater(job) : job)));
  }

  function handleCreateJob() {
    const nextJob = createWorkspaceJob(jobs.map((job) => job.title));
    setJobs((current) => [...current, nextJob]);
    startTransition(() => {
      setActiveJobId(nextJob.id);
    });
  }

  function handleDuplicateJob(jobId: string) {
    const source = jobs.find((job) => job.id === jobId);
    if (!source) {
      return;
    }

    const nextJob = createWorkspaceJob(
      jobs.map((job) => job.title),
      source,
    );
    setJobs((current) => [...current, nextJob]);
    startTransition(() => {
      setActiveJobId(nextJob.id);
    });
  }

  function handleDeleteJob(jobId: string) {
    if (jobs.length === 1) {
      const fallback = createWorkspaceJob([]);
      setJobs([fallback]);
      startTransition(() => {
        setActiveJobId(fallback.id);
      });
      return;
    }

    const nextJobs = jobs.filter((job) => job.id !== jobId);
    setJobs(nextJobs);

    if (jobId === activeJobId) {
      startTransition(() => {
        setActiveJobId(nextJobs[0]?.id ?? null);
      });
    }
  }

  function handleRenameJob(jobId: string, title: string) {
    updateJob(jobId, (job) => renameJob(job, title));
  }

  function handleUpdateJobParameter(jobId: string, column: JobColumn, value: unknown) {
    updateJob(jobId, (job) => applyJobColumnValue(job, column, value));
  }

  function handleTogglePlot(jobId: string, enabled: boolean) {
    updateJob(jobId, (job) => ({
      ...job,
      plotEnabled: enabled,
    }));
  }

  function handleActiveConfigChange(nextConfig: SimulationConfigInput) {
    if (!activeJob) {
      return;
    }

    updateJob(activeJob.id, (job) => ({
      ...job,
      config: nextConfig,
      title: nextConfig.name ? nextConfig.name : job.title,
    }));
  }

  function handleResetActiveJob() {
    if (!activeJob) {
      return;
    }

    const nextConfig = createDefaultConfig();
    nextConfig.name = activeJob.title;
    updateJob(activeJob.id, (job) => ({
      ...job,
      config: nextConfig,
    }));
  }

  async function handleRegisterRun() {
    if (!activeJob) {
      return;
    }

    setSubmittingJobId(activeJob.id);
    setSubmitErrors((current) => {
      const next = { ...current };
      delete next[activeJob.id];
      return next;
    });

    try {
      const created = await createRun(activeJob.config);
      setRunsById((current) => ({
        ...current,
        [created.run_id]: created,
      }));
      updateJob(activeJob.id, (job) => ({
        ...job,
        lastRunId: created.run_id,
        runHistory: [created.run_id, ...job.runHistory.filter((runId) => runId !== created.run_id)].slice(0, 8),
      }));
      setRunRefreshVersion((current) => current + 1);
    } catch (error) {
      setSubmitErrors((current) => ({
        ...current,
        [activeJob.id]: toErrorMessage(error),
      }));
    } finally {
      setSubmittingJobId(null);
    }
  }

  function handleSelectJob(jobId: string) {
    startTransition(() => {
      setActiveJobId(jobId);
    });
  }

  function handleSelectRunForJob(jobId: string, runId: string) {
    updateJob(jobId, (job) => ({
      ...job,
      lastRunId: runId,
    }));
  }

  function handleSelectPlotObservable(plotIndex: number, observable: string) {
    startTransition(() => {
      setComparePlots((current) =>
        current.map((plot, index) =>
          index === plotIndex
            ? {
                observable,
                series: null,
              }
            : plot,
        ),
      );
    });
  }

  function handleSelectPlotSeries(plotIndex: number, series: string) {
    startTransition(() => {
      setComparePlots((current) =>
        current.map((plot, index) =>
          index === plotIndex
            ? {
                ...plot,
                series,
              }
            : plot,
        ),
      );
    });
  }

  return (
    <main className="app-shell">
      <div className="app-backdrop" />
      <section className="hero">
        <div className="hero-main">
          <p className="hero-kicker">TDKB Workspace</p>
          <h1>Build, edit, and compare TDKB runs without losing the full parameter view.</h1>
          <p className="hero-copy">
            Switch drafts from tabs, edit every parameter inside compact cards, and pin time-evolution plots into a
            three-column comparison wall.
          </p>
        </div>
        <div className="hero-summary">
          <div className="hero-stat-card">
            <span className="hero-stat-label">Active Job</span>
            <strong>{activeJob?.title ?? "-"}</strong>
          </div>
          <div className="hero-stat-card">
            <span className="hero-stat-label">Solver</span>
            <strong>{activeJob?.config.solver ?? "-"}</strong>
          </div>
          <div className="hero-stat-card">
            <span className="hero-stat-label">Drafts</span>
            <strong>{jobs.length}</strong>
          </div>
          <div className="hero-stat-card">
            <span className="hero-stat-label">Compared Runs</span>
            <strong>{compareEntries.length}</strong>
          </div>
        </div>
      </section>

      <JobTabsBar
        jobs={jobs}
        activeJobId={activeJobId}
        runsById={runsById}
        onCreateJob={handleCreateJob}
        onSelectJob={handleSelectJob}
      />

      <JobSummaryTable
        jobs={jobs}
        activeJobId={activeJobId}
        runsById={runsById}
        parameterColumns={parameterColumns}
        showDifferentOnly={showDifferentOnly}
        onToggleShowDifferentOnly={setShowDifferentOnly}
        onSelectJob={handleSelectJob}
        onUpdateJobTitle={handleRenameJob}
        onUpdateJobParameter={handleUpdateJobParameter}
        onTogglePlot={handleTogglePlot}
        onDuplicateJob={handleDuplicateJob}
        onDeleteJob={handleDeleteJob}
      />

      <div className="workspace-grid">
        <div className="workspace-sidebar">
          <JobWorkbenchPanel
            job={activeJob}
            run={activeRun}
            runsById={runsById}
            submitting={submittingJobId === activeJob?.id}
            submitError={activeSubmitError ?? activeRunError}
            onTitleChange={(title) => {
              if (activeJob) {
                handleRenameJob(activeJob.id, title);
              }
            }}
            onRegisterRun={handleRegisterRun}
            onResetConfig={handleResetActiveJob}
            onDuplicateJob={() => {
              if (activeJob) {
                handleDuplicateJob(activeJob.id);
              }
            }}
            onDeleteJob={() => {
              if (activeJob) {
                handleDeleteJob(activeJob.id);
              }
            }}
            onTogglePlot={(value) => {
              if (activeJob) {
                handleTogglePlot(activeJob.id, value);
              }
            }}
            onSelectRun={(runId) => {
              if (activeJob) {
                handleSelectRunForJob(activeJob.id, runId);
              }
            }}
          />
          <ConfigPanel
            config={activeJob?.config ?? createDefaultConfig()}
            disabled={submittingJobId === activeJob?.id}
            onConfigChange={handleActiveConfigChange}
            onReset={handleResetActiveJob}
          />
        </div>

        <div className="workspace-main">
          <ObservableComparePanel
            observableOptions={observableOptions}
            plots={comparePlots}
            onSelectObservable={handleSelectPlotObservable}
            onSelectSeries={handleSelectPlotSeries}
            entries={compareEntries}
            dataByKey={compareDataByKey}
            loading={compareLoading}
            error={compareError}
          />
          <DiagnosticsPanel run={activeRun} />
        </div>
      </div>

      <GreenFunctionPanel
        run={activeRun}
        catalog={greenCatalog}
        catalogLoading={greenCatalogLoading}
        catalogError={greenCatalogError}
        selectedComponent={selectedGreenComponent}
        onSelectComponent={setSelectedGreenComponent}
        rowIndex={greenRowIndex}
        colIndex={greenColIndex}
        nambuStart={greenNambuStart}
        nambuWindow={greenNambuWindow}
        onRowIndexChange={setGreenRowIndex}
        onColIndexChange={setGreenColIndex}
        onNambuStartChange={setGreenNambuStart}
        onNambuWindowChange={setGreenNambuWindow}
        slice={greenSlice}
        sliceLoading={greenSliceLoading}
        sliceError={greenSliceError}
      />
    </main>
  );
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

function clampIndex(value: number, upper: number): number {
  return Math.min(Math.max(value, 0), upper);
}

function buildObservableCacheKey(runId: string, observable: string): string {
  return `${runId}::${observable}`;
}

function reconcileComparePlots(current: ComparePlotSelection[], observableOptions: string[]): ComparePlotSelection[] {
  const slotCount = Math.max(observableOptions.length, 3);
  const next = Array.from({ length: slotCount }, (_, index) => {
    const currentPlot = current[index];
    const observable =
      currentPlot?.observable && observableOptions.includes(currentPlot.observable)
        ? currentPlot.observable
        : (observableOptions[index] ?? null);
    const series = currentPlot?.observable === observable ? currentPlot.series : null;
    return { observable, series };
  });

  if (
    current.length === next.length &&
    current.every((plot, index) => plot.observable === next[index]?.observable && plot.series === next[index]?.series)
  ) {
    return current;
  }

  return next;
}

function sortObservableNames(names: string[]): string[] {
  const order = new Map<string, number>(SUPPORTED_OBSERVABLES.map((name, index) => [name, index]));
  return [...names].sort((left, right) => {
    const leftIndex = order.get(left);
    const rightIndex = order.get(right);

    if (leftIndex !== undefined && rightIndex !== undefined) {
      return leftIndex - rightIndex;
    }
    if (leftIndex !== undefined) {
      return -1;
    }
    if (rightIndex !== undefined) {
      return 1;
    }
    return left.localeCompare(right);
  });
}
