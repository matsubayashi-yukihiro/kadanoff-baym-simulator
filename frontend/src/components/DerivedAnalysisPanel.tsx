import type { ReactNode } from "react";
import type { DerivedAnalysisResultRecord } from "../api/types";

type DerivedAnalysisPanelProps = {
  title: string;
  status: "idle" | "launching" | "polling" | "succeeded" | "failed";
  error: string | null;
  result: DerivedAnalysisResultRecord | null;
  onLaunch: () => void;
  disabled?: boolean;
  children?: (result: DerivedAnalysisResultRecord) => ReactNode;
};

export function DerivedAnalysisPanel(props: DerivedAnalysisPanelProps) {
  const { title, status, error, result, onLaunch, disabled, children } = props;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Derived Analysis</p>
          <h2>{title}</h2>
        </div>
        <button
          type="button"
          className="ghost-button"
          onClick={onLaunch}
          disabled={disabled || status === "launching" || status === "polling"}
        >
          {status === "idle" ? "Compute" : status === "succeeded" ? "Recompute" : "Computing…"}
        </button>
      </div>

      {error && <p className="state-banner state-error">{error}</p>}

      {(status === "launching" || status === "polling") && (
        <p className="state-banner">Running analysis on backend…</p>
      )}

      {status === "succeeded" && result && children ? children(result) : null}

      {status === "idle" && (
        <div className="empty-card">
          <p>Click Compute to run this analysis on the backend.</p>
        </div>
      )}
    </section>
  );
}
