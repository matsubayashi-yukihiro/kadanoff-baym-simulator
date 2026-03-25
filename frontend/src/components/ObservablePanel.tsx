import { useEffect, useState } from "react";

import type {
  DerivedAnalysisResultRecord,
  ObservableCatalogResponse,
  ObservableResponse,
  RunDetail,
} from "../api/types";
import { useBackendCapabilities } from "../hooks/useBackendCapabilities";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { normalizeRunFftPreviewPayload } from "../lib/derivedPayload";
import { formatLabel, formatNumber } from "../lib/format";
import { isSuccessfulState } from "../lib/helpers";
import { getDefaultSpectrumSeriesLabel } from "../lib/spectrum";
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

function readNumericMetadata(metadata: Record<string, unknown>, key: string): number | null {
  const value = metadata[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildFftPreviewSummary(
  result: DerivedAnalysisResultRecord | null,
  fallbackObservable: string | null,
) {
  if (!result) return null;
  const metadata = (result.analysis.result_metadata ?? {}) as Record<string, unknown>;
  const sampleCount = readNumericMetadata(metadata, "sample_count");
  const frequencyResolution = readNumericMetadata(metadata, "frequency_resolution");
  return {
    observable: typeof metadata.observable === "string" ? metadata.observable : fallbackObservable,
    sourceSeriesLabel: typeof metadata.series_label === "string" ? metadata.series_label : null,
    sampleCount,
    frequencyResolution,
    dt:
      sampleCount !== null && frequencyResolution !== null && sampleCount > 0 && frequencyResolution > 0
        ? 1 / (sampleCount * frequencyResolution)
        : null,
    dominantFrequency: readNumericMetadata(metadata, "dominant_frequency"),
    meanSubtracted: metadata.mean_subtracted === true,
  };
}

export function ObservablePanel(props: ObservablePanelProps) {
  const {
    catalog, catalogLoading, catalogError,
    data, dataLoading, dataError,
    run, selectedObservable, onSelectObservable,
    overlayNames, onToggleOverlay, overlayData,
  } = props;

  const [activeTab, setActiveTab] = useState<ViewTab>("timeseries");
  const [selectedSpectrumSeriesLabel, setSelectedSpectrumSeriesLabel] = useState<string | null>(null);
  const { capabilities } = useBackendCapabilities();

  useEffect(() => {
    setSelectedSpectrumSeriesLabel(getDefaultSpectrumSeriesLabel(data));
  }, [data]);

  const overlayList: ObservableResponse[] = [];
  for (const name of overlayNames) {
    if (name === selectedObservable) continue;
    const d = overlayData.get(name);
    if (d) overlayList.push(d);
  }

  const runCompleted = run ? isSuccessfulState(run.state) : false;
  const runId = runCompleted ? (run?.run_id ?? null) : null;
  const resolvedSpectrumSeriesLabel = selectedSpectrumSeriesLabel ?? getDefaultSpectrumSeriesLabel(data);
  const capabilityBlockedReason = capabilities.supportsDerivedAnalysisLaunch
    ? null
    : "Backend does not advertise derived-analysis launch support in OpenAPI. Rebuild/restart backend to match frontend.";
  const {
    status: spectrumStatus,
    error: spectrumError,
    result: spectrumResult,
    launch: launchSpectrum,
  } = useDerivedAnalysis(
    runId && data ? "run" : null,
    runId,
    "fft_preview",
    {
      study_id: run?.research_metadata?.study_id ?? undefined,
      parameters: data
        ? {
          observable: data.name,
          ...(resolvedSpectrumSeriesLabel ? { series_label: resolvedSpectrumSeriesLabel } : {}),
        }
        : undefined,
    },
  );

  useEffect(() => {
    if (activeTab === "spectrum" && runId && data && !capabilityBlockedReason && spectrumStatus === "idle") {
      void launchSpectrum();
    }
  }, [activeTab, capabilityBlockedReason, data, launchSpectrum, runId, spectrumStatus]);

  const backendSpectrumPreview = spectrumResult
    ? (normalizeRunFftPreviewPayload(spectrumResult.payload) as ObservableResponse | null)
    : null;
  const spectrumSummary = buildFftPreviewSummary(spectrumResult, data?.name ?? null);

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

      {run && !isSuccessfulState(run.state) ? (
        <p className="state-banner">
          Observables will unlock after the run completes (`succeeded` or `succeeded_with_warnings`).
        </p>
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

      {run && isSuccessfulState(run.state) && catalog && catalog.observables.length === 0 ? (
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

          {capabilityBlockedReason ? (
            <p className="state-banner state-warning">{capabilityBlockedReason}</p>
          ) : null}
          {(spectrumStatus === "launching" || spectrumStatus === "polling") ? (
            <p className="state-banner">Loading backend FFT preview...</p>
          ) : null}
          {spectrumError ? <p className="state-banner state-error">{spectrumError}</p> : null}

          {backendSpectrumPreview && spectrumSummary ? (
            <>
              <div className="observable-meta">
                <div>
                  <span className="focus-key">Observable</span>
                  <span>{formatLabel(spectrumSummary.observable ?? data.name)}</span>
                </div>
                <div>
                  <span className="focus-key">Series</span>
                  <span>{formatLabel(spectrumSummary.sourceSeriesLabel ?? resolvedSpectrumSeriesLabel ?? "-")}</span>
                </div>
                <div>
                  <span className="focus-key">Samples</span>
                  <span>{spectrumSummary.sampleCount ?? "-"}</span>
                </div>
                <div>
                  <span className="focus-key">Frequency Resolution</span>
                  <span>{spectrumSummary.frequencyResolution !== null ? formatNumber(spectrumSummary.frequencyResolution, 4) : "-"}</span>
                </div>
                <div>
                  <span className="focus-key">dt</span>
                  <span>{spectrumSummary.dt !== null ? formatNumber(spectrumSummary.dt, 4) : "-"}</span>
                </div>
                <div>
                  <span className="focus-key">Dominant Nonzero Frequency</span>
                  <span>{spectrumSummary.dominantFrequency !== null ? formatNumber(spectrumSummary.dominantFrequency, 4) : "-"}</span>
                </div>
                <div>
                  <span className="focus-key">Preprocess</span>
                  <span>{spectrumSummary.meanSubtracted ? "mean-subtracted" : "none"}</span>
                </div>
              </div>
              <ObservablePlot data={backendSpectrumPreview} variant="compact" />
            </>
          ) : spectrumStatus === "succeeded" ? (
            <p className="state-banner state-error">Unexpected FFT payload format.</p>
          ) : (
            <div className="empty-card">
              <p>Backend FFT preview will appear here.</p>
              <p>Select a completed run and a saved observable to materialize <code>run/fft_preview</code>.</p>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
