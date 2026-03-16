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

export type ObservableCompareEntry = {
  jobId: string;
  jobTitle: string;
  runId: string;
  data: ObservableResponse;
};

type ObservableComparePanelProps = {
  observableOptions: string[];
  selectedObservable: string | null;
  onSelectObservable: (value: string) => void;
  selectedSeries: string | null;
  onSelectSeries: (value: string) => void;
  seriesOptions: string[];
  entries: ObservableCompareEntry[];
  loading: boolean;
  error: string | null;
};

export function ObservableComparePanel(props: ObservableComparePanelProps) {
  const {
    observableOptions,
    selectedObservable,
    onSelectObservable,
    selectedSeries,
    onSelectSeries,
    seriesOptions,
    entries,
    loading,
    error,
  } = props;

  const plottedEntries = entries
    .map((entry) => ({
      ...entry,
      series:
        entry.data.series.find((series) => series.label === selectedSeries) ??
        entry.data.series[0] ??
        null,
    }))
    .filter((entry) => entry.series !== null);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Compare</p>
          <h2>Observable Overlay</h2>
        </div>
        <div className="compare-toolbar">
          <label className="field compact-field">
            <span className="field-label">Observable</span>
            <select
              aria-label="Compare Observable"
              value={selectedObservable ?? ""}
              onChange={(event) => onSelectObservable(event.target.value)}
            >
              {observableOptions.map((option) => (
                <option key={option} value={option}>
                  {formatLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="field compact-field">
            <span className="field-label">Series</span>
            <select
              aria-label="Compare Series"
              value={selectedSeries ?? ""}
              onChange={(event) => onSelectSeries(event.target.value)}
              disabled={seriesOptions.length === 0}
            >
              {seriesOptions.map((option) => (
                <option key={option} value={option}>
                  {formatLabel(option)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {loading ? <p className="state-banner">Loading observable traces...</p> : null}
      {error ? <p className="state-banner state-error">{error}</p> : null}

      {plottedEntries.length === 0 ? (
        <div className="empty-card">
          <p>No completed jobs are selected for plotting.</p>
          <p>Toggle `plot` in the table and register at least one successful run.</p>
        </div>
      ) : (
        <ObservableOverlayChart entries={plottedEntries} selectedObservable={selectedObservable ?? "observable"} />
      )}
    </section>
  );
}

type ObservableOverlayChartProps = {
  entries: Array<
    ObservableCompareEntry & {
      series: ObservableResponse["series"][number];
    }
  >;
  selectedObservable: string;
};

function ObservableOverlayChart(props: ObservableOverlayChartProps) {
  const { entries, selectedObservable } = props;
  const width = 960;
  const height = 320;
  const padding = { top: 20, right: 18, bottom: 36, left: 60 };
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

  const xTicks = buildTicks(minTime, maxTime, 6);
  const yTicks = buildTicks(yMin, yMax, 5);

  return (
    <div className="chart-shell">
      <svg
        className="chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`compare-chart-${selectedObservable}`}
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
          <div key={entry.jobId} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: COMPARE_COLORS[index % COMPARE_COLORS.length] }} />
            <span>{entry.jobTitle}</span>
            <span className="legend-stat">{entry.series.label}</span>
            <span className="legend-stat">final {formatNumber(entry.series.values[entry.series.values.length - 1], 4)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildTicks(minValue: number, maxValue: number, count: number): number[] {
  if (count <= 1 || minValue === maxValue) {
    return [minValue];
  }

  const step = (maxValue - minValue) / (count - 1);
  return Array.from({ length: count }, (_, index) => minValue + step * index);
}
