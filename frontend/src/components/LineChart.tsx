import type { ObservableResponse } from "../api/types";
import { formatNumber } from "../lib/format";

const SERIES_COLORS = ["#0f4c5c", "#e36414", "#6b8f23", "#5f0f40", "#1b4332"];

type LineChartProps = {
  data: ObservableResponse;
};

export function LineChart(props: LineChartProps) {
  const { data } = props;
  const width = 720;
  const height = 280;
  const padding = { top: 18, right: 18, bottom: 32, left: 52 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const values = data.series.flatMap((series) => series.values);

  if (data.time.length === 0 || values.length === 0) {
    return <div className="empty-card">No samples available for this observable.</div>;
  }

  const minTime = Math.min(...data.time);
  const maxTime = Math.max(...data.time);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valuePadding = maxValue === minValue ? Math.max(Math.abs(maxValue) * 0.1, 1.0) : (maxValue - minValue) * 0.1;
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
      <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`observable-chart-${data.name}`}>
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

        {data.series.map((series, index) => {
          const path = series.values
            .map((value, valueIndex) => `${valueIndex === 0 ? "M" : "L"} ${scaleX(data.time[valueIndex])} ${scaleY(value)}`)
            .join(" ");
          return <path key={series.label} d={path} fill="none" stroke={SERIES_COLORS[index % SERIES_COLORS.length]} strokeWidth={2.5} />;
        })}
      </svg>

      <div className="chart-legend">
        {data.series.map((series, index) => (
          <div key={series.label} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: SERIES_COLORS[index % SERIES_COLORS.length] }} />
            <span>{series.label}</span>
            <span className="legend-stat">
              final {formatNumber(series.values[series.values.length - 1], 4)}
            </span>
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
