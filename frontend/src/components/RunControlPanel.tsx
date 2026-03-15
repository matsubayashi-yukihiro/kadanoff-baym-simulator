import type { RunDetail, RunSummary } from "../api/types";
import { formatDateTime } from "../lib/format";

type RunControlPanelProps = {
  isSubmitting: boolean;
  runs: RunSummary[];
  runsLoading: boolean;
  runsError: string | null;
  runLoading: boolean;
  runError: string | null;
  submitError: string | null;
  selectedRun: RunDetail | null;
  selectedRunId: string | null;
  onCreateRun: () => void;
  onRefresh: () => void;
  onSelectRun: (runId: string) => void;
};

export function RunControlPanel(props: RunControlPanelProps) {
  const {
    isSubmitting,
    runs,
    runsLoading,
    runsError,
    runLoading,
    runError,
    submitError,
    selectedRun,
    selectedRunId,
    onCreateRun,
    onRefresh,
    onSelectRun,
  } = props;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Execution</p>
          <h2>RunControlPanel</h2>
        </div>
        <div className="button-row">
          <button type="button" className="ghost-button" onClick={onRefresh}>
            Refresh
          </button>
          <button type="button" className="primary-button" onClick={onCreateRun} disabled={isSubmitting}>
            {isSubmitting ? "Submitting..." : "Create Run"}
          </button>
        </div>
      </div>

      {submitError ? <p className="state-banner state-error">{submitError}</p> : null}
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
                <span className="focus-key">Message</span>
                <span>{selectedRun.status_message ?? "-"}</span>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-card">
            <p>No run selected.</p>
            <p>Create one from the current config or pick an existing run below.</p>
          </div>
        )}
      </div>

      <div className="panel-subheader">
        <h3>Recent Runs</h3>
        {runLoading ? <span className="state-inline">Updating selected run...</span> : null}
      </div>

      {runsLoading ? <p className="state-banner">Loading runs...</p> : null}
      {runsError ? <p className="state-banner state-error">{runsError}</p> : null}
      {!runsLoading && runs.length === 0 ? (
        <div className="empty-card">
          <p>No saved runs yet.</p>
          <p>The list will populate after the first successful submission.</p>
        </div>
      ) : null}

      <div className="run-list">
        {runs.map((run) => (
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
          </button>
        ))}
      </div>
    </section>
  );
}
