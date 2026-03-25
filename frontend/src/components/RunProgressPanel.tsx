import type Plotly from "plotly.js-dist-min";

import type { RunDetail, RunProgressRecord } from "../api/types";
import { formatDateTime, formatLabel, formatNumber } from "../lib/format";
import { PlotlyChart, SERIES_COLORS } from "./charts/PlotlyChart";

type RunProgressPanelProps = {
  run: RunDetail | null;
  progress: RunProgressRecord | null;
  loading: boolean;
  error: string | null;
  isStale: boolean;
  staleDetails: {
    heartbeatAgeSeconds: number;
    phase: RunProgressRecord["phase"];
    statusLine: string | null;
  } | null;
};

const METRIC_ORDER = [
  "latest_fixed_point_residual",
  "latest_fixed_point_iterations",
  "latest_equation_residual",
  "latest_memory_norm",
  "current_dt",
  "latest_adaptive_error_estimate",
  "rejected_steps",
  "max_continuity_residual_so_far",
  "max_energy_work_mismatch_so_far",
  "thermal_branch_iterations",
  "history_integration_order",
  "current_time_index",
] as const;

export function RunProgressPanel(props: RunProgressPanelProps) {
  const { run, progress, loading, error, isStale, staleDetails } = props;

  if (!run || (run.state !== "queued" && run.state !== "running")) {
    return null;
  }

  const points = progress?.history ?? [];
  const x = points.map((point, index) => point.wall_seconds_elapsed ?? index);
  const physicalProgress = points.map((point) => (point.physical_progress_fraction ?? 0) * 100);
  const savedSamples = points.map((point) => point.saved_samples_written ?? 0);
  const chartData: Plotly.Data[] = [
    {
      type: "scatter",
      mode: "lines+markers",
      name: "Physical progress %",
      x,
      y: physicalProgress,
      line: { color: SERIES_COLORS[0], width: 2.5 },
      marker: { size: 5 },
    },
    {
      type: "scatter",
      mode: "lines",
      name: "Saved samples",
      x,
      y: savedSamples,
      yaxis: "y2",
      line: { color: SERIES_COLORS[1], width: 2, dash: "dot" },
    },
  ];
  const cards = buildMetricCards(progress);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Execution Telemetry</p>
          <h2>Live Run Progress</h2>
        </div>
        {progress ? <span className={`status-pill status-${progress.state}`}>{progress.phase}</span> : null}
      </div>

      {error ? <p className="state-banner state-error">{error}</p> : null}
      {isStale ? (
        <p className="state-banner state-warning">
          Progress updates look stale. Worker heartbeat has not advanced recently.
          {staleDetails ? (
            <>
              {" "}
              Last heartbeat age: {staleDetails.heartbeatAgeSeconds}s.
              {" "}
              phase={staleDetails.phase}
              {staleDetails.statusLine ? `, status=${staleDetails.statusLine}` : ""}.
            </>
          ) : null}
        </p>
      ) : null}
      {loading && !progress ? <p className="state-banner">Loading progress telemetry…</p> : null}

      {progress ? (
        <>
          <div className="run-progress-summary">
            <div>
              <span className="focus-key">Phase</span>
              <span>{formatLabel(progress.phase)}</span>
            </div>
            <div>
              <span className="focus-key">Elapsed</span>
              <span>{formatNumber(progress.wall_seconds_elapsed, 2)} s</span>
            </div>
            <div>
              <span className="focus-key">Physical Time</span>
              <span>
                {formatNumber(progress.physical_time_current ?? 0, 3)} / {formatNumber(progress.physical_time_final ?? 0, 3)}
              </span>
            </div>
            <div>
              <span className="focus-key">Completion</span>
              <span>{formatNumber((progress.physical_progress_fraction ?? 0) * 100, 1)}%</span>
            </div>
            <div>
              <span className="focus-key">Accepted Steps</span>
              <span>
                {progress.accepted_steps} / {progress.requested_steps}
              </span>
            </div>
            <div>
              <span className="focus-key">Updated</span>
              <span>{formatDateTime(progress.updated_at)}</span>
            </div>
          </div>

          <div className="run-progress-chart">
            <PlotlyChart
              data={chartData}
              layout={{
                title: { text: "Worker heartbeat and saved output" },
                xaxis: { title: { text: "Wall time (s)" } },
                yaxis: { title: { text: "Physical progress (%)" }, range: [0, 100] },
                yaxis2: {
                  title: { text: "Saved samples" },
                  overlaying: "y",
                  side: "right",
                  rangemode: "tozero",
                },
                height: 260,
                margin: { t: 40, r: 56, b: 48, l: 56 },
              }}
              style={{ width: "100%" }}
              useResizeHandler
            />
          </div>

          {progress.status_line ? <p className="hint-text">{progress.status_line}</p> : null}

          {cards.length > 0 ? (
            <div className="run-progress-metrics">
              {cards.map((card) => (
                <article key={card.key} className="metric-card">
                  <span className="metric-label">{card.label}</span>
                  <span className="metric-value">{card.value}</span>
                </article>
              ))}
            </div>
          ) : null}
        </>
      ) : error ? (
        <div className="empty-card">
          <p>Progress telemetry is unavailable.</p>
          <p>The connected backend did not return a progress record for this run.</p>
        </div>
      ) : (
        <div className="empty-card">
          <p>No progress telemetry yet.</p>
          <p>The worker will populate heartbeat data once the run starts advancing.</p>
        </div>
      )}
    </section>
  );
}

function buildMetricCards(progress: RunProgressRecord | null): Array<{ key: string; label: string; value: string }> {
  if (!progress) return [];
  const metrics = progress.solver_metrics ?? {};
  const rejectedSteps = progress.rejected_steps;
  const ordered = METRIC_ORDER
    .map((key) => [key, key === "rejected_steps" ? rejectedSteps : metrics[key]] as const)
    .filter(([, value]) => value !== null && value !== undefined);

  return ordered.slice(0, 6).map(([key, value]) => ({
    key,
    label: formatLabel(key),
    value: typeof value === "number" ? formatNumber(value, key.includes("iteration") ? 0 : 6) : String(value),
  }));
}
