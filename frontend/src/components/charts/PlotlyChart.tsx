import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

const BasePlot = createPlotlyComponent(Plotly);

export const SERIES_COLORS = ["#5ad8a6", "#f6bd16", "#5b8ff9", "#e8684a", "#9270ca"];
export const OVERLAY_COLORS = ["#36cfc9", "#ff9d4d", "#73d13d", "#ff85c0", "#69c0ff"];

const copyToClipboardButton = {
  name: "clipboard",
  title: "Copy to clipboard",
  icon: Plotly.Icons.camera,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  click: async (gd: any) => {
    try {
      const url = await Plotly.toImage(gd, {
        format: "png",
        scale: 2,
        width: gd.offsetWidth,
        height: gd.offsetHeight,
      } as Partial<Plotly.ToImgopts> as Plotly.ToImgopts);
      const res = await fetch(url);
      const blob = await res.blob();
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    } catch (err) {
      console.warn("Failed to copy plot to clipboard:", err);
    }
  },
};

function deepMergeDefaults(
  base: Record<string, unknown>,
  defaults: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...base };
  for (const key of Object.keys(defaults)) {
    if (!(key in result) || result[key] === undefined) {
      result[key] = defaults[key];
    } else if (
      typeof result[key] === "object" &&
      result[key] !== null &&
      !Array.isArray(result[key]) &&
      typeof defaults[key] === "object" &&
      defaults[key] !== null &&
      !Array.isArray(defaults[key])
    ) {
      result[key] = deepMergeDefaults(
        result[key] as Record<string, unknown>,
        defaults[key] as Record<string, unknown>,
      );
    }
  }
  return result;
}

const DEFAULT_LAYOUT: Partial<Plotly.Layout> = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "rgba(248, 251, 253, 0.5)",
  font: {
    family: '"IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif',
    color: "#14202b",
    size: 13,
  },
  margin: { t: 32, r: 24, b: 48, l: 64 },
  legend: {
    orientation: "h",
    yanchor: "bottom",
    y: 1.02,
    xanchor: "left",
    x: 0,
    font: { size: 11 },
  },
  xaxis: {
    gridcolor: "rgba(32, 52, 79, 0.08)",
    zerolinecolor: "rgba(32, 52, 79, 0.14)",
  },
  yaxis: {
    gridcolor: "rgba(32, 52, 79, 0.08)",
    zerolinecolor: "rgba(32, 52, 79, 0.14)",
  },
};

const DEFAULT_CONFIG: Partial<Plotly.Config> = {
  responsive: true,
  displaylogo: false,
  modeBarButtonsToAdd: [copyToClipboardButton],
};

export function PlotlyChart(props: React.ComponentProps<typeof BasePlot>) {
  const { config, layout, ...rest } = props;

  const mergedLayout = deepMergeDefaults(
    (layout ?? {}) as Record<string, unknown>,
    DEFAULT_LAYOUT as Record<string, unknown>,
  ) as Partial<Plotly.Layout>;

  const mergedConfig = {
    ...DEFAULT_CONFIG,
    ...config,
    modeBarButtonsToAdd: [
      copyToClipboardButton,
      ...(config?.modeBarButtonsToAdd ?? []),
    ],
  };

  return <BasePlot config={mergedConfig} layout={mergedLayout} {...rest} />;
}
