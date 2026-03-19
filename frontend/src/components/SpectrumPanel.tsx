import { useEffect, useState } from "react";

import type { ObservableResponse, RunDetail } from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";
import { buildSpectrumPreview, getDefaultSpectrumSeriesLabel } from "../lib/spectrum";
import { ObservablePlot } from "./charts/ObservablePlot";

type SpectrumPanelProps = {
  data: ObservableResponse | null;
  dataLoading: boolean;
  dataError: string | null;
  run: RunDetail | null;
};

export function SpectrumPanel(props: SpectrumPanelProps) {
  const { data, dataLoading, dataError, run } = props;
  const [selectedSeriesLabel, setSelectedSeriesLabel] = useState<string | null>(null);

  useEffect(() => {
    setSelectedSeriesLabel(getDefaultSpectrumSeriesLabel(data));
  }, [data]);

  const preview = data ? buildSpectrumPreview(data, selectedSeriesLabel) : null;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Derived Analysis</p>
          <h2>Spectrum Preview</h2>
        </div>
        {run ? <span className={`status-pill status-${run.state}`}>{run.state}</span> : null}
      </div>

      {!run ? (
        <div className="empty-card">
          <p>No run selected.</p>
          <p>Select a completed run to preview the FFT surface for the current observable.</p>
        </div>
      ) : null}

      {run && run.state !== "succeeded" ? (
        <p className="state-banner">Spectrum preview unlocks after the run reaches `succeeded`.</p>
      ) : null}
      {dataLoading ? <p className="state-banner">Building spectrum preview...</p> : null}
      {dataError ? <p className="state-banner state-error">{dataError}</p> : null}

      {data && data.series.length > 1 ? (
        <div className="chip-row" role="tablist" aria-label="Spectrum series selector">
          {data.series.map((series) => (
            <button
              key={series.label}
              type="button"
              className={`chip ${selectedSeriesLabel === series.label ? "chip-active" : ""}`}
              onClick={() => setSelectedSeriesLabel(series.label)}
            >
              {formatLabel(series.label)}
            </button>
          ))}
        </div>
      ) : null}

      {preview ? (
        <div className="observable-body">
          <p className="state-banner">
            Mean-subtracted local preview only. Persistent derived-analysis artifacts will move to backend storage once
            `derived-analyses` APIs land.
          </p>
          <div className="observable-meta">
            <div>
              <span className="focus-key">Observable</span>
              <span>{formatLabel(data?.name ?? "-")}</span>
            </div>
            <div>
              <span className="focus-key">Series</span>
              <span>{formatLabel(preview.sourceSeriesLabel)}</span>
            </div>
            <div>
              <span className="focus-key">Samples</span>
              <span>{preview.sampleCount}</span>
            </div>
            <div>
              <span className="focus-key">Frequency Resolution</span>
              <span>{formatNumber(preview.frequencyResolution, 4)}</span>
            </div>
            <div>
              <span className="focus-key">dt</span>
              <span>{formatNumber(preview.dt, 4)}</span>
            </div>
            <div>
              <span className="focus-key">Dominant Nonzero Frequency</span>
              <span>{formatNumber(preview.dominantFrequency, 4)}</span>
            </div>
            <div>
              <span className="focus-key">Preprocess</span>
              <span>{preview.meanSubtracted ? "mean-subtracted" : "none"}</span>
            </div>
          </div>
          <ObservablePlot data={preview.data} variant="compact" />
        </div>
      ) : null}

      {run && run.state === "succeeded" && data && !preview ? (
        <div className="empty-card">
          <p>No FFT preview available.</p>
          <p>The current observable requires at least two uniformly spaced samples.</p>
        </div>
      ) : null}
    </section>
  );
}
