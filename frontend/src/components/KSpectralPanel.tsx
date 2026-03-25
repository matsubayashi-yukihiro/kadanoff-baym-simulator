import { useEffect } from "react";
import type { RunDetail } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { useBackendCapabilities } from "../hooks/useBackendCapabilities";
import { normalizeKSpectralPayload } from "../lib/derivedPayload";
import { isSuccessfulState } from "../lib/helpers";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart } from "./charts/PlotlyChart";

type KSpectralPanelProps = {
  run: RunDetail | null;
  studyId?: string | null;
};

export function KSpectralPanel({ run, studyId }: KSpectralPanelProps) {
  const isKSpace = run?.config?.representation === "k_space";
  const runId = run && isSuccessfulState(run.state) ? run.run_id : null;
  const { capabilities } = useBackendCapabilities();
  const capabilityBlockedReason = capabilities.supportsDerivedAnalysisRunKspace
    ? null
    : "Backend does not advertise k-space derived-analysis support in OpenAPI. Rebuild/restart backend to match frontend.";

  const { status, error, result, launch } = useDerivedAnalysis(
    runId ? "run" : null,
    runId,
    "k_spectral_preview",
    { study_id: studyId ?? undefined },
  );

  // Auto-launch when run becomes available
  useEffect(() => {
    if (runId && isKSpace && !capabilityBlockedReason && status === "idle") {
      launch();
    }
  }, [runId, isKSpace, capabilityBlockedReason]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isKSpace) return null;

  return (
    <DerivedAnalysisPanel
      title="K-Path Spectral Function"
      status={status}
      error={error}
      result={result}
      onLaunch={launch}
      disabled={!runId}
      unavailableReason={capabilityBlockedReason}
    >
      {(res) => {
        const model = normalizeKSpectralPayload(res.payload);
        if (!model) {
          return <p className="state-banner state-error">Unexpected payload format.</p>;
        }

        return (
          <PlotlyChart
            data={[
              {
                type: "heatmap",
                z: model.z,
                x: model.x,
                y: model.y,
                colorscale: "Viridis",
                showscale: true,
                name: "A(k,ω)",
              },
            ]}
            layout={{
              title: { text: "Occupied Spectral Function A(k,ω)" },
              xaxis: {
                title: { text: model.xAxisTitle },
                tickmode: "array",
                tickvals: model.xTickVals ?? [],
                ticktext: model.xTickText ?? [],
              },
              yaxis: { title: { text: model.yAxisTitle } },
              height: 380,
            }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        );
      }}
    </DerivedAnalysisPanel>
  );
}
