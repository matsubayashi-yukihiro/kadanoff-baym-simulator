import type { ObservableResponse } from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";

const SERIES_COLORS = ["#5ad8a6", "#f6bd16", "#5b8ff9", "#e8684a", "#9270ca"];
const OVERLAY_COLORS = ["#36cfc9", "#ff9d4d", "#73d13d", "#ff85c0", "#69c0ff"];

type LineChartProps = {
  data: ObservableResponse;
  overlays?: ObservableResponse[];
  variant?: "primary" | "compact";
};

export function LineChart(props: LineChartProps) {
  const { data, overlays = [], variant = "primary" } = props;
  const width = 1000;
  const height = variant === "primary" ? 390 : 310;
  const padding =
    variant === "primary"
      ? { top: 24, right: 22, bottom: 52, left: 72 }
      : { top: 20, right: 18, bottom: 46, left: 64 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const allDatasets = [data, ...overlays];
  const allValues = allDatasets.flatMap((d) => d.series.flatMap((s) => s.values));
  const allTimes = allDatasets.flatMap((d) => d.time);

  if (data.time.length === 0 || allValues.length === 0) {
    return <div className="empty-card">No samples available for this observable.</div>;
  }

  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const valuePadding = maxValue === minValue ? Math.max(Math.abs(maxValue) * 0.1, 1.0) : (maxValue - minValue) * 0.1;
  const yMin = minValue - valuePadding;
  const yMax = maxValue + valuePadding;

  function scaleX(time: number): number {
    if (maxTime === minTime) return padding.left + plotWidth / 2;
    return padding.left + ((time - minTime) / (maxTime - minTime)) * plotWidth;
  }

  function scaleY(value: number): number {
    if (yMax === yMin) return padding.top + plotHeight / 2;
    return padding.top + (1 - (value - yMin) / (yMax - yMin)) * plotHeight;
  }

  const xTicks = buildTicks(minTime, maxTime, 5);
  const yTicks = buildTicks(yMin, yMax, 5);
  const zeroInRange = yMin < 0 && yMax > 0;
  const gradientId = `chart-gradient-${data.name.replace(/[^a-z0-9_-]/gi, "-")}-${variant}`;

  type LegendEntry = { label: string; color: string; finalValue: number };
  const legendEntries: LegendEntry[] = [];

  data.series.forEach((series, index) => {
    legendEntries.push({
      label: series.label,
      color: SERIES_COLORS[index % SERIES_COLORS.length],
      finalValue: series.values[series.values.length - 1],
    });
  });
  overlays.forEach((overlay, overlayIndex) => {
    overlay.series.forEach((series, seriesIndex) => {
      legendEntries.push({
        label: `${formatLabel(overlay.name)}: ${series.label}`,
        color: OVERLAY_COLORS[(overlayIndex * 2 + seriesIndex) % OVERLAY_COLORS.length],
        finalValue: series.values[series.values.length - 1],
      });
    });
  });

  // Downsample hover points when there are many samples
  const hoverStride = Math.max(1, Math.floor(data.time.length / 80));

  return (
    <div className={`chart-shell chart-shell-${variant}`}>
      <svg
        className="chart"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`observable-chart-${data.name}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#53b88a" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#53b88a" stopOpacity="0" />
          </linearGradient>
        </defs>
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
              <text x={x} y={height - padding.bottom + 18} textAnchor="middle" className="chart-axis-label">
                {formatNumber(tick, 3)}
              </text>
            </g>
          );
        })}

        {zeroInRange ? (
          <line
            x1={padding.left}
            y1={scaleY(0)}
            x2={width - padding.right}
            y2={scaleY(0)}
            className="chart-zero-line"
          />
        ) : null}

        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} className="chart-axis" />
        <line x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} className="chart-axis" />

        <text
          x={width / 2}
          y={height - 4}
          textAnchor="middle"
          className="chart-axis-title"
        >
          t
        </text>
        <text
          x={14}
          y={padding.top + plotHeight / 2}
          textAnchor="middle"
          className="chart-axis-title"
          transform={`rotate(-90, 14, ${padding.top + plotHeight / 2})`}
        >
          {formatLabel(data.name)}
        </text>

        {data.series.map((series, index) => {
          const color = SERIES_COLORS[index % SERIES_COLORS.length];
          const pathD = series.values
            .map((value, vi) => `${vi === 0 ? "M" : "L"} ${scaleX(data.time[vi])} ${scaleY(value)}`)
            .join(" ");
          const areaD = `${pathD} L ${scaleX(data.time[data.time.length - 1])} ${height - padding.bottom} L ${scaleX(data.time[0])} ${height - padding.bottom} Z`;
          return (
            <g key={series.label}>
              {index === 0 ? <path d={areaD} fill={`url(#${gradientId})`} opacity={0.9} /> : null}
              <path d={pathD} fill="none" stroke={color} strokeWidth={variant === "primary" ? 2.7 : 2.2} strokeLinejoin="round" strokeLinecap="round" />
              {series.values.map((value, vi) =>
                vi % hoverStride !== 0 && vi !== series.values.length - 1 ? null : (
                  <circle
                    key={vi}
                    cx={scaleX(data.time[vi])}
                    cy={scaleY(value)}
                    r={4}
                    fill={color}
                    opacity={0}
                    className="chart-hover-point"
                  >
                    <title>{`${series.label}\nt = ${formatNumber(data.time[vi], 4)}\nvalue = ${formatNumber(value, 6)}`}</title>
                  </circle>
                ),
              )}
            </g>
          );
        })}

        {/* Overlay series lines */}
        {overlays.map((overlay, overlayIndex) =>
          overlay.series.map((series, seriesIndex) => {
            const color = OVERLAY_COLORS[(overlayIndex * 2 + seriesIndex) % OVERLAY_COLORS.length];
            const overlayStride = Math.max(1, Math.floor(overlay.time.length / 80));
            const pathD = series.values
              .map((value, vi) => `${vi === 0 ? "M" : "L"} ${scaleX(overlay.time[vi])} ${scaleY(value)}`)
              .join(" ");
            return (
              <g key={`${overlay.name}-${series.label}`}>
                <path d={pathD} fill="none" stroke={color} strokeWidth={2} strokeDasharray="6 3" />
                {series.values.map((value, vi) =>
                  vi % overlayStride !== 0 && vi !== series.values.length - 1 ? null : (
                    <circle
                      key={vi}
                      cx={scaleX(overlay.time[vi])}
                      cy={scaleY(value)}
                      r={4}
                      fill={color}
                      opacity={0}
                      className="chart-hover-point"
                    >
                      <title>{`${formatLabel(overlay.name)}: ${series.label}\nt = ${formatNumber(overlay.time[vi], 4)}\nvalue = ${formatNumber(value, 6)}`}</title>
                    </circle>
                  ),
                )}
              </g>
            );
          }),
        )}
      </svg>

      <div className="chart-legend">
        {legendEntries.map((entry) => (
          <div key={entry.label} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: entry.color }} />
            <span>{entry.label}</span>
            <span className="legend-stat">
              final {formatNumber(entry.finalValue, 4)}
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
