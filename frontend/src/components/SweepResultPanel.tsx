import { useEffect } from "react";
import type { RunSummary, SweepRecord } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { useBackendCapabilities } from "../hooks/useBackendCapabilities";
import { normalizeSweepTrArpesHeatmapPayload } from "../lib/derivedPayload";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart } from "./charts/PlotlyChart";

type SweepResultPanelProps = {
  sweep: SweepRecord | null;
  allRuns: RunSummary[];
  studyId?: string | null;
};

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);

export function SweepResultPanel({ sweep, allRuns, studyId }: SweepResultPanelProps) {
  const { capabilities } = useBackendCapabilities();
  const sweepSucceeded = sweep?.state === "succeeded";
  const capabilityBlockedReason = capabilities.supportsDerivedAnalysisRunKspace
    ? null
    : "Backend does not advertise k-space derived-analysis support in OpenAPI. Rebuild/restart backend to match frontend.";

  const { status, error, result, launch } = useDerivedAnalysis(
    sweep ? "sweep" : null,
    sweep?.sweep_id ?? null,
    "tr_arpes_heatmap",
    { study_id: studyId ?? undefined },
  );

  useEffect(() => {
    if (sweepSucceeded && !capabilityBlockedReason && status === "idle") {
      launch();
    }
  }, [sweepSucceeded, capabilityBlockedReason]); // eslint-disable-line react-hooks/exhaustive-deps

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
          unavailableReason={capabilityBlockedReason}
        >
          {(res) => {
            const model = normalizeSweepTrArpesHeatmapPayload(res.payload);
            if (!model) {
              return <p className="state-banner state-error">Unexpected payload format.</p>;
            }

            return (
              <PlotlyChart
                data={[
                  {
                    type: "heatmap",
                    z: model.z,
                    x: model.x,
                    y: model.y,
                    colorscale: "Plasma",
                    showscale: true,
                    name: "tr-ARPES",
                  },
                ]}
                layout={{
                  title: { text: `tr-ARPES vs ${sweep.parameter_label}` },
                  xaxis: { title: { text: sweep.parameter_label } },
                  yaxis: { title: { text: model.yAxisTitle } },
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
