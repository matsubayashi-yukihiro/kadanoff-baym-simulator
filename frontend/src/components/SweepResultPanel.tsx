import { useEffect } from "react";
import type { RunSummary, SweepRecord } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart } from "./charts/PlotlyChart";

type SweepResultPanelProps = {
  sweep: SweepRecord | null;
  allRuns: RunSummary[];
  studyId?: string | null;
};

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function SweepResultPanel({ sweep, allRuns, studyId }: SweepResultPanelProps) {
  const sweepSucceeded = sweep?.state === "succeeded";

  const { status, error, result, launch } = useDerivedAnalysis(
    sweep ? "sweep" : null,
    sweep?.sweep_id ?? null,
    "sweep/tr_arpes_heatmap",
    { study_id: studyId ?? undefined },
  );

  useEffect(() => {
    if (sweepSucceeded && status === "idle") {
      launch();
    }
  }, [sweepSucceeded]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sweep) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Result</p>
            <h2>Sweep Results</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>Select or launch a sweep to view results.</p>
        </div>
      </section>
    );
  }

  const childRunIds = sweep.child_run_ids ?? [];
  const values = sweep.values ?? [];

  return (
    <div className="space-y-4">
      {/* Child run status grid */}
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Parameter Sweep</p>
            <h2>{sweep.name}</h2>
          </div>
          <span className={`status-pill status-${sweep.state}`}>{sweep.state}</span>
        </div>
        <div className="panel-grid panel-grid-3" style={{ gap: "0.5rem" }}>
          {childRunIds.map((runId, i) => {
            const run = allRuns.find((r) => r.run_id === runId);
            const value = values[i];
            return (
              <div key={runId} className="run-card" style={{ cursor: "default" }}>
                <div className="run-card-top">
                  <span className="run-card-name" style={{ fontSize: "0.8rem" }}>
                    {sweep.parameter_label}={String(value ?? i)}
                  </span>
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
        {!TERMINAL_STATES.has(sweep.state) && (
          <p className="state-banner">Waiting for sweep runs to complete…</p>
        )}
      </section>

      {/* tr-ARPES heatmap */}
      {sweepSucceeded && (
        <DerivedAnalysisPanel
          title="tr-ARPES Sweep Heatmap"
          status={status}
          error={error}
          result={result}
          onLaunch={launch}
        >
          {(res) => {
            const payload = res.payload as {
              parameter_values?: (string | number | boolean)[];
              omega?: number[];
              heatmap?: number[][];
            };

            if (!payload.heatmap || !payload.omega || !payload.parameter_values) {
              return <p className="state-banner state-error">Unexpected payload format.</p>;
            }

            const nParam = payload.parameter_values.length;
            const nOmega = payload.omega.length;

            // heatmap[param_idx][omega_idx] → plotly z[omega_idx][param_idx]
            const z: number[][] = Array.from({ length: nOmega }, (_, wi) =>
              Array.from({ length: nParam }, (_, pi) => payload.heatmap![pi][wi]),
            );

            return (
              <PlotlyChart
                data={[
                  {
                    type: "heatmap",
                    z,
                    x: payload.parameter_values.map(String),
                    y: payload.omega,
                    colorscale: "Plasma",
                    showscale: true,
                    name: "tr-ARPES",
                  },
                ]}
                layout={{
                  title: { text: `tr-ARPES vs ${sweep.parameter_label}` },
                  xaxis: { title: { text: sweep.parameter_label } },
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
