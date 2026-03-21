import type { RunDetail, RunSummary } from "../api/types";
import { formatDateTime } from "../lib/format";

type RunControlPanelProps = {
  runs: RunSummary[];
  runsLoading: boolean;
  runsError: string | null;
  runLoading: boolean;
  runError: string | null;
  submitError: string | null;
  cancelError: string | null;
  selectedRun: RunDetail | null;
  selectedRunId: string | null;
  onRefresh: () => void;
  onSelectRun: (runId: string) => void;
};

export function RunControlPanel(props: RunControlPanelProps) {
  const {
    runs,
    runsLoading,
    runsError,
    runLoading,
    runError,
    submitError,
    cancelError,
    selectedRun,
    selectedRunId,
    onRefresh,
    onSelectRun,
  } = props;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Registry</p>
          <h2>Runs And Queue</h2>
        </div>
        <button type="button" className="ghost-button" onClick={onRefresh}>
          Refresh
        </button>
      </div>

      {submitError ? <p className="state-banner state-error">{submitError}</p> : null}
      {cancelError ? <p className="state-banner state-error">{cancelError}</p> : null}
      {runError ? <p className="state-banner state-error">{runError}</p> : null}

      <div className="run-focus">
        {selectedRun ? (
          <>
            <div className="focus-header">
              <div>
                <p className="focus-label">{selectedRun.name || selectedRun.run_id}</p>
                <p className="focus-meta">Run ID: {selectedRun.run_id}</p>
              </div>
              <span className={`status-pill status-${selectedRun.state}`}>{selectedRun.state}</span>
            </div>
            <div className="focus-grid">
              <div>
                <span className="focus-key">Created</span>
                <span>{formatDateTime(selectedRun.created_at)}</span>
              </div>
              <div>
                <span className="focus-key">Updated</span>
                <span>{formatDateTime(selectedRun.updated_at)}</span>
              </div>
              <div>
                <span className="focus-key">Solver</span>
                <span>{selectedRun.solver}</span>
              </div>
              <div>
                <span className="focus-key">Representation</span>
                <span>{selectedRun.config?.representation ?? "real_space"}</span>
              </div>
              <div>
                <span className="focus-key">Message</span>
                <span>{selectedRun.status_message ?? "-"}</span>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-card">
            <p>No run selected.</p>
            <p>Launch the current draft or pick an existing artifact below.</p>
          </div>
        )}
      </div>

      <div className="panel-subheader">
        <h3>Recent Runs</h3>
        {runLoading ? <span className="state-inline">Updating selected run...</span> : null}
      </div>

      {runsLoading && runs.length === 0 ? <p className="state-banner">Loading runs...</p> : null}
      {runsError ? <p className="state-banner state-error">{runsError}</p> : null}
      {!runsLoading && runs.length === 0 ? (
        <div className="empty-card">
          <p>No saved runs yet.</p>
          <p>The registry fills in as soon as the first run is launched.</p>
        </div>
      ) : null}

      {runs.length > 8 && (
        <p className="text-xs text-ink-muted mb-1">Showing last 8 runs</p>
      )}
      <div className="run-list">
        {runs.slice(-8).map((run) => {
          const role = run.research_metadata?.run_role;
          const vStatus = run.research_metadata?.validation_status;
          return (
            <button
              key={run.run_id}
              type="button"
              className={`run-card ${run.run_id === selectedRunId ? "run-card-selected" : ""}`}
              onClick={() => onSelectRun(run.run_id)}
            >
              <div className="run-card-top">
                <span className="run-card-name">{run.name || run.run_id}</span>
                <span className={`status-pill status-${run.state}`}>{run.state}</span>
              </div>
              <div className="run-card-meta">
                <span>{run.solver}</span>
                <span>{formatDateTime(run.updated_at)}</span>
              </div>
              {(role || (vStatus && vStatus !== "unchecked")) ? (
                <div className="hero-badge-row" style={{ marginTop: "0.3rem" }}>
                  {role ? <span className="signal-badge">{role}</span> : null}
                  {vStatus && vStatus !== "unchecked" ? (
                    <span className={`validation-pill validation-${vStatus}`}>{vStatus}</span>
                  ) : null}
                </div>
              ) : null}
            </button>
          );
        })}
      </div>
    </section>
  );
}
