declare module "plotly.js-dist-min" {
  import Plotly from "plotly.js";
  export default Plotly;
}

declare module "react-plotly.js/factory" {
  import type Plotly from "plotly.js";
  import type { Component } from "react";

  interface PlotParams {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    frames?: Plotly.Frame[];
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: { data: Plotly.Data[]; layout: Partial<Plotly.Layout> }, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: { data: Plotly.Data[]; layout: Partial<Plotly.Layout> }, graphDiv: HTMLElement) => void;
    onPurge?: (figure: { data: Plotly.Data[]; layout: Partial<Plotly.Layout> }, graphDiv: HTMLElement) => void;
    onError?: (error: Error) => void;
    revision?: number;
  }

  function createPlotlyComponent(plotly: typeof Plotly): new (props: PlotParams) => Component<PlotParams>;
  export default createPlotlyComponent;
}
