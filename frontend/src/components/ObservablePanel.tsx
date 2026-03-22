import { useEffect, useState } from "react";

import type { ObservableCatalogResponse, ObservableResponse, RunDetail } from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";
import { buildSpectrumPreview, getDefaultSpectrumSeriesLabel } from "../lib/spectrum";
import { ObservablePlot } from "./charts/ObservablePlot";

type ViewTab = "timeseries" | "spectrum";

type ObservablePanelProps = {
  catalog: ObservableCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  data: ObservableResponse | null;
  dataLoading: boolean;
  dataError: string | null;
  run: RunDetail | null;
  selectedObservable: string | null;
  onSelectObservable: (name: string) => void;
  overlayNames: ReadonlySet<string>;
  onToggleOverlay: (name: string) => void;
  overlayData: ReadonlyMap<string, ObservableResponse>;
};

export function ObservablePanel(props: ObservablePanelProps) {
  const {
    catalog, catalogLoading, catalogError,
    data, dataLoading, dataError,
    run, selectedObservable, onSelectObservable,
    overlayNames, onToggleOverlay, overlayData,
  } = props;

  const [activeTab, setActiveTab] = useState<ViewTab>("timeseries");
  const [selectedSpectrumSeriesLabel, setSelectedSpectrumSeriesLabel] = useState<string | null>(null);

  useEffect(() => {
    setSelectedSpectrumSeriesLabel(getDefaultSpectrumSeriesLabel(data));
  }, [data]);

  const overlayList: ObservableResponse[] = [];
  for (const name of overlayNames) {
    if (name === selectedObservable) continue;
    const d = overlayData.get(name);
    if (d) overlayList.push(d);
  }

  const spectrumPreview = data ? buildSpectrumPreview(data, selectedSpectrumSeriesLabel) : null;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Signals</p>
          <h2>Observable Readout</h2>
        </div>
        {run ? <span className={`status-pill status-${run.state}`}>{run.state}</span> : null}
      </div>

      {!run ? (
        <div className="empty-card">
          <p>No observable source selected.</p>
          <p>Select a completed run to inspect saved time-series output.</p>
        </div>
      ) : null}

      {run && run.state !== "succeeded" ? (
        <p className="state-banner">Observables will unlock after the run reaches `succeeded`.</p>
      ) : null}
      {catalogLoading ? <p className="state-banner">Loading observable catalog...</p> : null}
      {catalogError ? <p className="state-banner state-error">{catalogError}</p> : null}

      {catalog && catalog.observables.length > 0 ? (
        <>
          <div className="chip-row" role="tablist" aria-label="Observable selector">
            {catalog.observables.map((name) => {
              const isPrimary = selectedObservable === name;
              const isOverlay = overlayNames.has(name);
              return (
                <button
                  key={name}
                  type="button"
                  className={`chip ${isPrimary ? "chip-active" : isOverlay ? "chip-overlay" : ""}`}
                  onClick={(e) => {
                    if (e.shiftKey || e.metaKey || e.ctrlKey) {
                      if (!isPrimary) onToggleOverlay(name);
                    } else {
                      onSelectObservable(name);
                    }
                  }}
                  title={isPrimary ? "Primary observable" : "Click to select, Shift+click to overlay"}
                >
                  {formatLabel(name)}
                </button>
              );
            })}
          </div>
          {catalog.observables.length > 1 ? (
            <p className="hint-text">Shift+click chips to overlay multiple observables on the chart.</p>
          ) : null}
        </>
      ) : null}

      {run && run.state === "succeeded" && catalog && catalog.observables.length === 0 ? (
        <div className="empty-card">
          <p>No observables were saved for this run.</p>
          <p>Adjust the observable list in the config and resubmit.</p>
        </div>
      ) : null}

      {/* View tabs — only show when data is available */}
      {data ? (
        <div className="chip-row" role="tablist" aria-label="View mode">
          <button
            type="button"
            className={`chip ${activeTab === "timeseries" ? "chip-active" : ""}`}
            onClick={() => setActiveTab("timeseries")}
          >
            Time Series
          </button>
          <button
            type="button"
            className={`chip ${activeTab === "spectrum" ? "chip-active" : ""}`}
            onClick={() => setActiveTab("spectrum")}
          >
            Spectrum
          </button>
        </div>
      ) : null}

      {dataLoading ? <p className="state-banner">Loading time series...</p> : null}
      {dataError ? <p className="state-banner state-error">{dataError}</p> : null}

      {/* Time Series tab */}
      {data && activeTab === "timeseries" ? (
        <div className="observable-body">
          <div className="observable-meta">
            <div>
              <span className="focus-key">Observable</span>
              <span>{formatLabel(data.name)}</span>
            </div>
            <div>
              <span className="focus-key">Samples</span>
              <span>{data.time.length}</span>
            </div>
            <div>
              <span className="focus-key">Series</span>
              <span>{data.series.length}{overlayList.length > 0 ? ` + ${overlayList.length} overlay` : ""}</span>
            </div>
          </div>
          <ObservablePlot data={data} overlays={overlayList} variant="primary" />
        </div>
      ) : null}

      {/* Spectrum tab */}
      {data && activeTab === "spectrum" ? (
        <div className="observable-body">
          <p className="state-banner">
            Client-side FFT preview (mean-subtracted). Backend-cached FFT artifacts are available via{" "}
            <code>run/fft_preview</code> derived analysis — replacement pending payload format alignment.
          </p>

          {/* Series selector for multi-series observables */}
          {data.series.length > 1 ? (
            <div className="chip-row" role="tablist" aria-label="Spectrum series selector">
              {data.series.map((series) => (
                <button
                  key={series.label}
                  type="button"
                  className={`chip ${selectedSpectrumSeriesLabel === series.label ? "chip-active" : ""}`}
                  onClick={() => setSelectedSpectrumSeriesLabel(series.label)}
                >
                  {formatLabel(series.label)}
                </button>
              ))}
            </div>
          ) : null}

          {spectrumPreview ? (
            <>
              <div className="observable-meta">
                <div>
                  <span className="focus-key">Observable</span>
                  <span>{formatLabel(data.name)}</span>
                </div>
                <div>
                  <span className="focus-key">Series</span>
                  <span>{formatLabel(spectrumPreview.sourceSeriesLabel)}</span>
                </div>
                <div>
                  <span className="focus-key">Samples</span>
                  <span>{spectrumPreview.sampleCount}</span>
                </div>
                <div>
                  <span className="focus-key">Frequency Resolution</span>
                  <span>{formatNumber(spectrumPreview.frequencyResolution, 4)}</span>
                </div>
                <div>
                  <span className="focus-key">dt</span>
                  <span>{formatNumber(spectrumPreview.dt, 4)}</span>
                </div>
                <div>
                  <span className="focus-key">Dominant Nonzero Frequency</span>
                  <span>{formatNumber(spectrumPreview.dominantFrequency, 4)}</span>
                </div>
                <div>
                  <span className="focus-key">Preprocess</span>
                  <span>{spectrumPreview.meanSubtracted ? "mean-subtracted" : "none"}</span>
                </div>
              </div>
              <ObservablePlot data={spectrumPreview.data} variant="compact" />
            </>
          ) : (
            <div className="empty-card">
              <p>No FFT preview available.</p>
              <p>The current observable requires at least two uniformly spaced samples.</p>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
