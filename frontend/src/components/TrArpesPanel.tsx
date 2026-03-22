import { useEffect, useState } from "react";
import type { RunDetail } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { useBackendCapabilities } from "../hooks/useBackendCapabilities";
import { normalizeTrArpesPreviewPayload } from "../lib/derivedPayload";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart } from "./charts/PlotlyChart";

type TrArpesPanelProps = {
  run: RunDetail | null;
  studyId?: string | null;
};

export function TrArpesPanel({ run, studyId }: TrArpesPanelProps) {
  const isKSpace = run?.config?.representation === "k_space";
  const runId = run?.state === "succeeded" ? (run?.run_id ?? null) : null;
  const { capabilities } = useBackendCapabilities();
  const capabilityBlockedReason = capabilities.supportsDerivedAnalysisRunKspace
    ? null
    : "Backend does not advertise k-space derived-analysis support in OpenAPI. Rebuild/restart backend to match frontend.";

  const [probeCenter, setProbeCenter] = useState<number | null>(null);

  const params = probeCenter !== null ? { probe_center: probeCenter } : {};

  const { status, error, result, launch } = useDerivedAnalysis(
    runId ? "run" : null,
    runId,
    "tr_arpes_preview",
    { study_id: studyId ?? undefined, parameters: params },
  );

  // Auto-launch when run becomes available
  useEffect(() => {
    if (runId && isKSpace && !capabilityBlockedReason && status === "idle") {
      launch();
    }
  }, [runId, isKSpace, capabilityBlockedReason]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isKSpace) return null;

  const payload = result?.payload as { probe_center_used?: number; probe_center?: number } | undefined;

  const tFinal = run?.config?.time?.t_final ?? 1;

  return (
    <DerivedAnalysisPanel
      title="tr-ARPES Intensity"
      status={status}
      error={error}
      result={result}
      onLaunch={launch}
      disabled={!runId}
      unavailableReason={capabilityBlockedReason}
    >
      {(res) => {
        const model = normalizeTrArpesPreviewPayload(res.payload);
        if (!model) {
          return <p className="state-banner state-error">Unexpected payload format.</p>;
        }

        return (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
              <label htmlFor="probe-center-input" className="field-label" style={{ minWidth: "7rem" }}>
                Probe center
              </label>
              <input
                id="probe-center-input"
                type="number"
                step="0.1"
                min={0}
                max={tFinal}
                value={probeCenter ?? payload?.probe_center_used ?? payload?.probe_center ?? 0}
                onChange={(e) => setProbeCenter(Number(e.target.value))}
                style={{ width: "7rem" }}
              />
              <button
                type="button"
                className="ghost-button"
                onClick={() => launch()}
                disabled={status === "launching" || status === "polling"}
              >
                Update
              </button>
            </div>
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  z: model.z,
                  x: model.x,
                  y: model.y,
                  colorscale: "Plasma",
                  showscale: true,
                  name: "I(delay, ω)",
                },
              ]}
              layout={{
                title: { text: "tr-ARPES I(probe delay, ω)" },
                xaxis: {
                  title: { text: model.xAxisTitle },
                  tickmode: model.xTickVals?.length ? "array" : undefined,
                  tickvals: model.xTickVals,
                  ticktext: model.xTickText,
                },
                yaxis: { title: { text: model.yAxisTitle } },
                height: 380,
              }}
              style={{ width: "100%" }}
              useResizeHandler
            />
          </>
        );
      }}
    </DerivedAnalysisPanel>
  );
}
