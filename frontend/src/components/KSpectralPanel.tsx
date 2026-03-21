import { useEffect } from "react";
import type { RunDetail } from "../api/types";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";
import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";
import { PlotlyChart } from "./charts/PlotlyChart";

type KSpectralPanelProps = {
  run: RunDetail | null;
  studyId?: string | null;
};

export function KSpectralPanel({ run, studyId }: KSpectralPanelProps) {
  const isKSpace = run?.config?.representation === "k_space";
  const runId = run?.state === "succeeded" ? (run?.run_id ?? null) : null;

  const { status, error, result, launch } = useDerivedAnalysis(
    runId ? "run" : null,
    runId,
    "run/k_spectral_preview",
    { study_id: studyId ?? undefined },
  );

  // Auto-launch when run becomes available
  useEffect(() => {
    if (runId && isKSpace && status === "idle") {
      launch();
    }
  }, [runId, isKSpace]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isKSpace) return null;

  return (
    <DerivedAnalysisPanel
      title="K-Path Spectral Function"
      status={status}
      error={error}
      result={result}
      onLaunch={launch}
      disabled={!runId}
    >
      {(res) => {
        const payload = res.payload as {
          k_labels?: string[];
          k_indices?: number[];
          omega?: number[];
          spectrum?: number[][];
        };

        if (!payload.spectrum || !payload.omega || !payload.k_labels) {
          return <p className="state-banner state-error">Unexpected payload format.</p>;
        }

        const nK = payload.spectrum.length;
        const nOmega = payload.omega.length;

        // Build z as 2D array [k_index][omega_index] → plotly wants [omega_index][k_index]
        const z: number[][] = Array.from({ length: nOmega }, (_, wi) =>
          Array.from({ length: nK }, (_, ki) => payload.spectrum![ki][wi]),
        );

        return (
          <PlotlyChart
            data={[
              {
                type: "heatmap",
                z,
                x: Array.from({ length: nK }, (_, i) => i),
                y: payload.omega,
                colorscale: "Viridis",
                showscale: true,
                name: "A(k,ω)",
              },
            ]}
            layout={{
              title: { text: "Occupied Spectral Function A(k,ω)" },
              xaxis: {
                title: { text: "k-path index" },
                tickmode: "array",
                tickvals: payload.k_indices ?? [],
                ticktext: payload.k_labels,
              },
              yaxis: { title: { text: "ω" } },
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
