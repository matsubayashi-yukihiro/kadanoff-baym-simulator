import { useEffect } from "react";
import type { JobGroupRecord, RunSummary } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart, SERIES_COLORS } from "./charts/PlotlyChart";

type JobGroupResultPanelProps = {
  group: JobGroupRecord | null;
  allRuns: RunSummary[];
  studyId?: string | null;
};

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function JobGroupResultPanel({ group, allRuns, studyId }: JobGroupResultPanelProps) {
  const groupSucceeded = group?.state === "succeeded";
  const isKSpace = group?.variants?.some((v) => {
    if (!v.run_id) return false;
    const run = allRuns.find((r) => r.run_id === v.run_id);
    return (run?.lattice as { boundary?: string } | undefined)?.boundary === "periodic";
  });

  const { status, error, result, launch } = useDerivedAnalysis(
    group ? "job_group" : null,
    group?.group_id ?? null,
    "job_group/k_spectral_compare",
    { study_id: studyId ?? undefined },
  );

  // Auto-launch when group succeeds and k-space applies
  useEffect(() => {
    if (groupSucceeded && isKSpace && status === "idle") {
      launch();
    }
  }, [groupSucceeded, isKSpace]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!group) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Result</p>
            <h2>Job Group Results</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>Select or launch a job group to view results.</p>
        </div>
      </section>
    );
  }

  // Show child run status grid
  const variants = group.variants ?? [];
  const childRunIds = group.child_run_ids ?? [];

  return (
    <div className="space-y-4">
      {/* Child run status */}
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Job Group</p>
            <h2>{group.name}</h2>
          </div>
          <span className={`status-pill status-${group.state}`}>{group.state}</span>
        </div>
        <div className="run-list">
          {variants.map((variant, i) => {
            const runId = variant.run_id ?? childRunIds[i];
            const run = runId ? allRuns.find((r) => r.run_id === runId) : null;
            return (
              <div key={variant.label} className="run-card">
                <div className="run-card-top">
                  <span className="run-card-name">{variant.label}</span>
                  {run ? (
                    <span className={`status-pill status-${run.state}`}>{run.state}</span>
                  ) : runId ? (
                    <span className="status-pill status-queued">queued</span>
                  ) : (
                    <span className="status-pill">—</span>
                  )}
                </div>
                {variant.description && (
                  <p className="run-card-meta" style={{ fontSize: "0.8rem" }}>{variant.description}</p>
                )}
              </div>
            );
          })}
          {variants.length === 0 && childRunIds.length > 0 &&
            childRunIds.map((runId) => {
              const run = allRuns.find((r) => r.run_id === runId);
              return (
                <div key={runId} className="run-card">
                  <div className="run-card-top">
                    <span className="run-card-name">{run?.name || runId}</span>
                    {run ? (
                      <span className={`status-pill status-${run.state}`}>{run.state}</span>
                    ) : (
                      <span className="status-pill status-queued">queued</span>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
        {!TERMINAL_STATES.has(group.state) && (
          <p className="state-banner">Waiting for child runs to complete…</p>
        )}
      </section>

      {/* K-spectral compare — only when succeeded and k-space */}
      {groupSucceeded && isKSpace && (
        <DerivedAnalysisPanel
          title="K-Path Spectral Compare"
          status={status}
          error={error}
          result={result}
          onLaunch={launch}
        >
          {(res) => {
            const payload = res.payload as {
              variants?: Array<{
                label: string;
                k_labels?: string[];
                k_indices?: number[];
                omega?: number[];
                spectrum?: number[][];
              }>;
            };

            if (!payload.variants?.length) {
              return <p className="state-banner state-error">No variant data in payload.</p>;
            }

            const traces = payload.variants.map((v, i) => {
              const nK = v.spectrum?.length ?? 0;
              const nOmega = v.omega?.length ?? 0;
              const z: number[][] = Array.from({ length: nOmega }, (_, wi) =>
                Array.from({ length: nK }, (_, ki) => v.spectrum![ki][wi]),
              );
              return {
                type: "heatmap" as const,
                z,
                x: Array.from({ length: nK }, (_, k) => k),
                y: v.omega ?? [],
                colorscale: "Viridis",
                showscale: i === 0,
                name: v.label,
                visible: (i === 0 ? true : "legendonly") as boolean | "legendonly",
                colorbar: i === 0 ? {} : undefined,
              };
            });

            const first = payload.variants[0];
            return (
              <PlotlyChart
                data={traces}
                layout={{
                  title: { text: "A(k,ω) — Variant Comparison" },
                  xaxis: {
                    title: { text: "k-path index" },
                    tickmode: "array",
                    tickvals: first.k_indices ?? [],
                    ticktext: first.k_labels,
                  },
                  yaxis: { title: { text: "ω" } },
                  height: 400,
                }}
                style={{ width: "100%" }}
                useResizeHandler
              />
            );
          }}
        </DerivedAnalysisPanel>
      )}
    </div>
  );
}
