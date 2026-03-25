import { useEffect, useState } from "react";

import type { DerivedAnalysisResultRecord, ObservableResponse, RunDetail } from "../api/types";
import { useBackendCapabilities } from "../hooks/useBackendCapabilities";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { normalizeRunFftPreviewPayload } from "../lib/derivedPayload";
import { formatLabel, formatNumber } from "../lib/format";
import { isSuccessfulState } from "../lib/helpers";
import { getDefaultSpectrumSeriesLabel } from "../lib/spectrum";
import { ObservablePlot } from "./charts/ObservablePlot";

type SpectrumPanelProps = {
  data: ObservableResponse | null;
  dataLoading: boolean;
  dataError: string | null;
  run: RunDetail | null;
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

export function SpectrumPanel(props: SpectrumPanelProps) {
  const { data, dataLoading, dataError, run } = props;
  const [selectedSeriesLabel, setSelectedSeriesLabel] = useState<string | null>(null);
  const { capabilities } = useBackendCapabilities();

  useEffect(() => {
    setSelectedSeriesLabel(getDefaultSpectrumSeriesLabel(data));
  }, [data]);

  const runCompleted = run ? isSuccessfulState(run.state) : false;
  const runId = runCompleted ? (run?.run_id ?? null) : null;
  const resolvedSelectedSeriesLabel = selectedSeriesLabel ?? getDefaultSpectrumSeriesLabel(data);
  const capabilityBlockedReason = capabilities.supportsDerivedAnalysisLaunch
    ? null
    : "Backend does not advertise derived-analysis launch support in OpenAPI. Rebuild/restart backend to match frontend.";
  const { status, error, result, launch } = useDerivedAnalysis(
    runId && data ? "run" : null,
    runId,
    "fft_preview",
    {
      study_id: run?.research_metadata?.study_id ?? undefined,
      parameters: data
        ? {
          observable: data.name,
          ...(resolvedSelectedSeriesLabel ? { series_label: resolvedSelectedSeriesLabel } : {}),
        }
        : undefined,
    },
  );

  useEffect(() => {
    if (runId && data && !capabilityBlockedReason && status === "idle") {
      void launch();
    }
  }, [capabilityBlockedReason, data, launch, runId, status]);

  const preview = result
    ? (normalizeRunFftPreviewPayload(result.payload) as ObservableResponse | null)
    : null;
  const previewSummary = buildFftPreviewSummary(result, data?.name ?? null);

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

      {run && !runCompleted ? (
        <p className="state-banner">
          Spectrum preview unlocks after the run completes (`succeeded` or `succeeded_with_warnings`).
        </p>
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
      {capabilityBlockedReason ? <p className="state-banner state-warning">{capabilityBlockedReason}</p> : null}
      {(status === "launching" || status === "polling") ? (
        <p className="state-banner">Loading backend FFT preview...</p>
      ) : null}
      {error ? <p className="state-banner state-error">{error}</p> : null}

      {preview && previewSummary ? (
        <div className="observable-body">
          <div className="observable-meta">
            <div>
              <span className="focus-key">Observable</span>
              <span>{formatLabel(previewSummary.observable ?? data?.name ?? "-")}</span>
            </div>
            <div>
              <span className="focus-key">Series</span>
              <span>{formatLabel(previewSummary.sourceSeriesLabel ?? resolvedSelectedSeriesLabel ?? "-")}</span>
            </div>
            <div>
              <span className="focus-key">Samples</span>
              <span>{previewSummary.sampleCount ?? "-"}</span>
            </div>
            <div>
              <span className="focus-key">Frequency Resolution</span>
              <span>{previewSummary.frequencyResolution !== null ? formatNumber(previewSummary.frequencyResolution, 4) : "-"}</span>
            </div>
            <div>
              <span className="focus-key">dt</span>
              <span>{previewSummary.dt !== null ? formatNumber(previewSummary.dt, 4) : "-"}</span>
            </div>
            <div>
              <span className="focus-key">Dominant Nonzero Frequency</span>
              <span>{previewSummary.dominantFrequency !== null ? formatNumber(previewSummary.dominantFrequency, 4) : "-"}</span>
            </div>
            <div>
              <span className="focus-key">Preprocess</span>
              <span>{previewSummary.meanSubtracted ? "mean-subtracted" : "none"}</span>
            </div>
          </div>
          <ObservablePlot data={preview} variant="compact" />
        </div>
      ) : status === "succeeded" ? (
        <p className="state-banner state-error">Unexpected FFT payload format.</p>
      ) : null}

      {run && runCompleted && data && !preview && status === "idle" ? (
        <div className="empty-card">
          <p>Backend FFT preview will appear here.</p>
          <p>Select a completed run and a saved observable to materialize <code>run/fft_preview</code>.</p>
        </div>
      ) : null}
    </section>
  );
}
