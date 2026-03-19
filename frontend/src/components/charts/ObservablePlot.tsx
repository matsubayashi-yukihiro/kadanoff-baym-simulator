import type Plotly from "plotly.js-dist-min";

import type { ObservableResponse } from "../../api/types";
import { formatLabel } from "../../lib/format";
import { OVERLAY_COLORS, PlotlyChart, SERIES_COLORS } from "./PlotlyChart";

type ObservablePlotProps = {
  data: ObservableResponse;
  overlays?: ObservableResponse[];
  variant?: "primary" | "compact";
};

export function ObservablePlot(props: ObservablePlotProps) {
  const { data, overlays = [], variant = "primary" } = props;

  const isFrequencyDomain = data.name.toLowerCase().includes("fft");
  const xLabel = isFrequencyDomain ? "frequency" : "t";
  const yLabel = formatLabel(data.name);
  const height = variant === "primary" ? 400 : 320;

  const traces: Plotly.Data[] = [];

  // Primary series
  for (let i = 0; i < data.series.length; i++) {
    const series = data.series[i];
    traces.push({
      x: data.time,
      y: series.values,
      type: "scatter",
      mode: "lines",
      name: formatLabel(series.label),
      line: { color: SERIES_COLORS[i % SERIES_COLORS.length], width: 1.5 },
      hovertemplate: `${xLabel}: %{x}<br>value: %{y}<extra>${formatLabel(series.label)}</extra>`,
    });
  }

  // Overlay series
  for (const overlay of overlays) {
    for (let i = 0; i < overlay.series.length; i++) {
      const series = overlay.series[i];
      traces.push({
        x: overlay.time,
        y: series.values,
        type: "scatter",
        mode: "lines",
        name: `${formatLabel(overlay.name)} / ${formatLabel(series.label)}`,
        line: {
          color: OVERLAY_COLORS[i % OVERLAY_COLORS.length],
          width: 1.5,
          dash: "dash",
        },
        hovertemplate: `${xLabel}: %{x}<br>value: %{y}<extra>${formatLabel(overlay.name)} / ${formatLabel(series.label)}</extra>`,
      });
    }
  }

  const layout: Partial<Plotly.Layout> = {
    plot_bgcolor: "#0f1722",
    paper_bgcolor: "transparent",
    font: { color: "#a7b6c2" },
    xaxis: {
      title: { text: xLabel },
      gridcolor: "rgba(167, 182, 194, 0.10)",
      zerolinecolor: "rgba(167, 182, 194, 0.18)",
      tickfont: { color: "#a7b6c2" },
    },
    yaxis: {
      title: { text: yLabel },
      gridcolor: "rgba(167, 182, 194, 0.10)",
      zerolinecolor: "rgba(167, 182, 194, 0.18)",
      tickfont: { color: "#a7b6c2" },
    },
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: 1.02,
      xanchor: "left",
      x: 0,
      font: { size: 11, color: "#a7b6c2" },
    },
  };

  return (
    <PlotlyChart
      data={traces}
      layout={layout}
      useResizeHandler={true}
      style={{ width: "100%", height: `${height}px` }}
    />
  );
}
