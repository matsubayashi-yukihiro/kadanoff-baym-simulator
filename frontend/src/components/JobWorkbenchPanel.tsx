import type { RunDetail } from "../api/types";
import { formatDateTime } from "../lib/format";
import { shortRunId, type WorkspaceJob } from "../lib/workspace";

type JobWorkbenchPanelProps = {
  job: WorkspaceJob | null;
  run: RunDetail | null;
  runsById: Record<string, RunDetail>;
  submitting: boolean;
  submitError: string | null;
  onTitleChange: (title: string) => void;
  onRegisterRun: () => void;
  onResetConfig: () => void;
  onDuplicateJob: () => void;
  onDeleteJob: () => void;
  onTogglePlot: (value: boolean) => void;
  onSelectRun: (runId: string) => void;
};

export function JobWorkbenchPanel(props: JobWorkbenchPanelProps) {
  const {
    job,
    run,
    runsById,
    submitting,
    submitError,
    onTitleChange,
    onRegisterRun,
    onResetConfig,
    onDuplicateJob,
    onDeleteJob,
    onTogglePlot,
    onSelectRun,
  } = props;

  if (!job) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Workbench</p>
            <h2>Active Job</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>No job selected.</p>
          <p>Pick a row or a tab to edit and register a run.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Workbench</p>
          <h2>Active Job</h2>
        </div>
        <span className={`status-pill status-${run?.state ?? "queued"}`}>{run?.state ?? "draft"}</span>
      </div>

      <label className="field">
        <span className="field-label">Job Name</span>
        <input
          aria-label="Active Job Name"
          value={job.title}
          onChange={(event) => onTitleChange(event.target.value)}
        />
      </label>

      <div className="job-status-grid">
        <div className="metric-card">
          <span className="metric-label">Selected Run</span>
          <span className="metric-value">{shortRunId(job.lastRunId)}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Plot Overlay</span>
          <label className="toggle-pill toggle-pill-compact">
            <input
              aria-label="Active Job Plot Toggle"
              type="checkbox"
              checked={job.plotEnabled}
              onChange={(event) => onTogglePlot(event.target.checked)}
            />
            <span>{job.plotEnabled ? "Included" : "Hidden"}</span>
          </label>
        </div>
        <div className="metric-card">
          <span className="metric-label">Last Updated</span>
          <span className="metric-value">{formatDateTime(run?.updated_at)}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Solver</span>
          <span className="metric-value">{job.config.solver}</span>
        </div>
      </div>

      <div className="button-row workbench-actions">
        <button type="button" className="primary-button" onClick={onRegisterRun} disabled={submitting}>
          {submitting ? "Registering..." : "Register Run"}
        </button>
        <button type="button" className="ghost-button" onClick={onResetConfig}>
          Reset Draft
        </button>
        <button type="button" className="ghost-button" onClick={onDuplicateJob}>
          Duplicate Job
        </button>
        <button type="button" className="ghost-button" onClick={onDeleteJob}>
          Delete Job
        </button>
      </div>

      {submitError ? <p className="state-banner state-error">{submitError}</p> : null}

      <div className="panel-subheader">
        <h3>Recent Runs</h3>
      </div>

      {job.runHistory.length === 0 ? (
        <div className="empty-card">
          <p>No run registered from this tab yet.</p>
          <p>Once submitted, you can switch the active result for plotting and diagnostics.</p>
        </div>
      ) : (
        <div className="run-history">
          {job.runHistory.map((runId) => {
            const item = runsById[runId];
            return (
              <button
                key={runId}
                type="button"
                className={`run-history-button ${job.lastRunId === runId ? "run-history-button-active" : ""}`}
                onClick={() => onSelectRun(runId)}
              >
                <span>{shortRunId(runId)}</span>
                <span className={`status-pill status-${item?.state ?? "queued"}`}>{item?.state ?? "loading"}</span>
                <span className="state-inline">{formatDateTime(item?.updated_at)}</span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
