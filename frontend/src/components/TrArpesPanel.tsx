import { useEffect, useState } from "react";
import type { RunDetail } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart } from "./charts/PlotlyChart";

type TrArpesPanelProps = {
  run: RunDetail | null;
  studyId?: string | null;
};

export function TrArpesPanel({ run, studyId }: TrArpesPanelProps) {
  const isKSpace = run?.config?.representation === "k_space";
  const runId = run?.state === "succeeded" ? (run?.run_id ?? null) : null;

  const [probeCenter, setProbeCenter] = useState<number | null>(null);

  const params = probeCenter !== null ? { probe_center: probeCenter } : {};

  const { status, error, result, launch } = useDerivedAnalysis(
    runId ? "run" : null,
    runId,
    "run/tr_arpes_preview",
    { study_id: studyId ?? undefined, parameters: params },
  );

  // Auto-launch when run becomes available
  useEffect(() => {
    if (runId && isKSpace && status === "idle") {
      launch();
    }
  }, [runId, isKSpace]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isKSpace) return null;

  const payload = result?.payload as {
    probe_centers?: number[];
    omega?: number[];
    intensity?: number[][];
    probe_center_used?: number;
  } | undefined;

  const tFinal = run?.config?.time?.t_final ?? 1;

  return (
    <DerivedAnalysisPanel
      title="tr-ARPES Intensity"
      status={status}
      error={error}
      result={result}
      onLaunch={launch}
      disabled={!runId}
    >
      {(res) => {
        const p = res.payload as {
          probe_centers?: number[];
          omega?: number[];
          intensity?: number[][];
          probe_center_used?: number;
        };

        if (!p.intensity || !p.omega || !p.probe_centers) {
          return <p className="state-banner state-error">Unexpected payload format.</p>;
        }

        const nDelay = p.probe_centers.length;
        const nOmega = p.omega.length;

        // intensity shape: [n_delay][n_omega]
        const z: number[][] = Array.from({ length: nOmega }, (_, wi) =>
          Array.from({ length: nDelay }, (_, di) => p.intensity![di][wi]),
        );

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
                value={probeCenter ?? p.probe_center_used ?? 0}
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
                  z,
                  x: p.probe_centers,
                  y: p.omega,
                  colorscale: "Plasma",
                  showscale: true,
                  name: "I(delay, ω)",
                },
              ]}
              layout={{
                title: { text: "tr-ARPES I(probe delay, ω)" },
                xaxis: { title: { text: "probe delay" } },
                yaxis: { title: { text: "ω" } },
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

