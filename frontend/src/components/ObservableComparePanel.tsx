import type { ObservableResponse } from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";

const COMPARE_COLORS = [
  "#0f4c5c",
  "#e36414",
  "#2d6a4f",
  "#5f0f40",
  "#2b2d42",
  "#6b8f23",
  "#bc4749",
  "#3a506b",
];

export type ComparePlotSelection = {
  observable: string | null;
  series: string | null;
};

type ObservableCompareEntry = {
  jobId: string;
  jobTitle: string;
  runId: string;
};

type ObservableComparePanelProps = {
  observableOptions: string[];
  plots: ComparePlotSelection[];
  onSelectObservable: (plotIndex: number, value: string) => void;
  onSelectSeries: (plotIndex: number, value: string) => void;
  entries: ObservableCompareEntry[];
  dataByKey: Record<string, ObservableResponse>;
  loading: boolean;
  error: string | null;
};

type ResolvedPlotEntry = ObservableCompareEntry & {
  data: ObservableResponse;
  series: ObservableResponse["series"][number];
};

export function ObservableComparePanel(props: ObservableComparePanelProps) {
  const {
    observableOptions,
    plots,
    onSelectObservable,
    onSelectSeries,
    entries,
    dataByKey,
    loading,
    error,
  } = props;

  return (
    <section className="panel compare-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Compare</p>
          <h2>Observable Plot Wall</h2>
        </div>
        <span className="compare-grid-meta">{plots.length} charts</span>
      </div>

      <p className="summary-note">
        Each plot card keeps its own observable selector so you can build a custom three-column comparison layout.
      </p>

      {entries.length === 0 ? (
        <div className="empty-card">
          <p>No completed jobs are selected for plotting.</p>
          <p>Enable plot on a job card and register at least one successful run.</p>
        </div>
      ) : null}

      {entries.length > 0 && observableOptions.length === 0 ? (
        <div className="empty-card">
          <p>No saved observables are available yet.</p>
          <p>Successful runs will populate plot choices automatically.</p>
        </div>
      ) : null}

      {loading ? <p className="state-banner">Loading observable traces...</p> : null}
      {error ? <p className="state-banner state-error">{error}</p> : null}

      {entries.length > 0 && observableOptions.length > 0 ? (
        <div className="compare-grid">
          {plots.map((plot, plotIndex) => {
            const plotData = buildPlotData(plot, entries, dataByKey);
            const plotTitle = plot.observable ? formatLabel(plot.observable) : "Select observable";

            return (
              <article key={`plot-${plotIndex}`} className="compare-card">
                <div className="compare-card-header">
                  <div>
                    <p className="eyebrow">Plot {String(plotIndex + 1).padStart(2, "0")}</p>
                    <h3>{plotTitle}</h3>
                  </div>
                  <span className="compare-card-count">{plotData.entries.length} runs</span>
                </div>

                <div className="plot-button-row" role="toolbar" aria-label={`Plot ${plotIndex + 1} observable selector`}>
                  {observableOptions.map((option) => (
                    <button
                      key={`${plotIndex}-${option}`}
                      type="button"
                      className={`chip ${plot.observable === option ? "chip-active" : ""}`}
                      onClick={() => onSelectObservable(plotIndex, option)}
                    >
                      {formatLabel(option)}
                    </button>
                  ))}
                </div>

                {plotData.seriesOptions.length > 1 ? (
                  <div className="plot-series-row" role="toolbar" aria-label={`Plot ${plotIndex + 1} series selector`}>
                    {plotData.seriesOptions.map((series) => (
                      <button
                        key={`${plotIndex}-${series}`}
                        type="button"
                        className={`chip chip-secondary ${plotData.selectedSeries === series ? "chip-active" : ""}`}
                        onClick={() => onSelectSeries(plotIndex, series)}
                      >
                        {formatLabel(series)}
                      </button>
                    ))}
                  </div>
                ) : null}

                {!plot.observable ? (
                  <div className="empty-card">
                    <p>Select an observable for this slot.</p>
                    <p>The card will overlay the same physical quantity across the selected runs.</p>
                  </div>
                ) : plotData.entries.length === 0 ? (
                  <div className="empty-card">
                    <p>No samples are loaded for this observable yet.</p>
                    <p>Wait for the run to finish or choose another observable.</p>
                  </div>
                ) : (
                  <ObservableOverlayChart
                    plotIndex={plotIndex}
                    entries={plotData.entries}
                    selectedObservable={plot.observable}
                    selectedSeries={plotData.selectedSeries ?? "series"}
                  />
                )}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

type ObservableOverlayChartProps = {
  plotIndex: number;
  entries: ResolvedPlotEntry[];
  selectedObservable: string;
  selectedSeries: string;
};

function ObservableOverlayChart(props: ObservableOverlayChartProps) {
  const { plotIndex, entries, selectedObservable, selectedSeries } = props;
  const width = 720;
  const height = 260;
  const padding = { top: 18, right: 18, bottom: 34, left: 56 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const times = entries.flatMap((entry) => entry.data.time);
  const values = entries.flatMap((entry) => entry.series.values);

  if (times.length === 0 || values.length === 0) {
    return <div className="empty-card">No samples were saved for the selected comparison.</div>;
  }

  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valuePadding = maxValue === minValue ? Math.max(Math.abs(maxValue) * 0.1, 1.0) : (maxValue - minValue) * 0.08;
  const yMin = minValue - valuePadding;
  const yMax = maxValue + valuePadding;

  function scaleX(time: number): number {
    if (maxTime === minTime) {
      return padding.left + plotWidth / 2;
    }
    return padding.left + ((time - minTime) / (maxTime - minTime)) * plotWidth;
  }

  function scaleY(value: number): number {
    if (yMax === yMin) {
      return padding.top + plotHeight / 2;
    }
    return padding.top + (1 - (value - yMin) / (yMax - yMin)) * plotHeight;
  }

  const xTicks = buildTicks(minTime, maxTime, 5);
  const yTicks = buildTicks(yMin, yMax, 5);

  return (
    <div className="chart-shell">
      <svg
        className="chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`compare-chart-${plotIndex + 1}-${selectedObservable}`}
      >
        <rect x={0} y={0} width={width} height={height} rx={18} className="chart-frame" />
        {yTicks.map((tick) => {
          const y = scaleY(tick);
          return (
            <g key={`y-${tick}`}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} className="chart-grid" />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" className="chart-axis-label">
                {formatNumber(tick, 3)}
              </text>
            </g>
          );
        })}
        {xTicks.map((tick) => {
          const x = scaleX(tick);
          return (
            <g key={`x-${tick}`}>
              <line x1={x} y1={padding.top} x2={x} y2={height - padding.bottom} className="chart-grid chart-grid-vertical" />
              <text x={x} y={height - 10} textAnchor="middle" className="chart-axis-label">
                {formatNumber(tick, 3)}
              </text>
            </g>
          );
        })}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="chart-axis" />
        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          className="chart-axis"
        />

        {entries.map((entry, index) => {
          const path = entry.series.values
            .map((value, valueIndex) => {
              const time = entry.data.time[valueIndex] ?? minTime;
              return `${valueIndex === 0 ? "M" : "L"} ${scaleX(time)} ${scaleY(value)}`;
            })
            .join(" ");

          return (
            <path
              key={`${entry.jobId}-${entry.series.label}`}
              d={path}
              fill="none"
              stroke={COMPARE_COLORS[index % COMPARE_COLORS.length]}
              strokeWidth={2.6}
              strokeLinecap="round"
            />
          );
        })}
      </svg>

      <div className="chart-legend compare-legend">
        {entries.map((entry, index) => (
          <div key={`${entry.jobId}-${entry.series.label}`} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: COMPARE_COLORS[index % COMPARE_COLORS.length] }} />
            <span>{entry.jobTitle}</span>
            <span className="legend-stat">{formatLabel(selectedSeries)}</span>
            <span className="legend-stat">final {formatNumber(entry.series.values[entry.series.values.length - 1], 4)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildPlotData(
  plot: ComparePlotSelection,
  entries: ObservableCompareEntry[],
  dataByKey: Record<string, ObservableResponse>,
): {
  entries: ResolvedPlotEntry[];
  seriesOptions: string[];
  selectedSeries: string | null;
} {
  if (!plot.observable) {
    return {
      entries: [],
      seriesOptions: [],
      selectedSeries: null,
    };
  }

  const loadedEntries = entries
    .map((entry) => {
      const data = dataByKey[buildObservableCacheKey(entry.runId, plot.observable!)];
      if (!data) {
        return null;
      }
      return {
        ...entry,
        data,
      };
    })
    .filter((entry): entry is ObservableCompareEntry & { data: ObservableResponse } => entry !== null);

  const seriesOptions = Array.from(
    new Set(loadedEntries.flatMap((entry) => entry.data.series.map((series) => series.label))),
  );
  const selectedSeries = resolveSeriesLabel(plot.series, seriesOptions);
  const plottedEntries = loadedEntries
    .map((entry) => {
      const series = entry.data.series.find((item) => item.label === selectedSeries) ?? entry.data.series[0] ?? null;
      if (!series) {
        return null;
      }
      return {
        ...entry,
        series,
      };
    })
    .filter((entry): entry is ResolvedPlotEntry => entry !== null);

  return {
    entries: plottedEntries,
    seriesOptions,
    selectedSeries,
  };
}

function resolveSeriesLabel(requested: string | null, seriesOptions: string[]): string | null {
  if (seriesOptions.length === 0) {
    return null;
  }
  if (requested && seriesOptions.includes(requested)) {
    return requested;
  }
  if (seriesOptions.includes("magnitude")) {
    return "magnitude";
  }
  if (seriesOptions.includes("total")) {
    return "total";
  }
  if (seriesOptions.includes("mean")) {
    return "mean";
  }
  return seriesOptions[0];
}

function buildObservableCacheKey(runId: string, observable: string): string {
  return `${runId}::${observable}`;
}

function buildTicks(minValue: number, maxValue: number, count: number): number[] {
  if (count <= 1 || minValue === maxValue) {
    return [minValue];
  }

  const step = (maxValue - minValue) / (count - 1);
  return Array.from({ length: count }, (_, index) => minValue + step * index);
}
