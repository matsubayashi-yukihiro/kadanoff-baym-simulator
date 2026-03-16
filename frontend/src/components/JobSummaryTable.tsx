import type { RunDetail } from "../api/types";
import { formatLabel } from "../lib/format";
import {
  columnValueDiffers,
  shortRunId,
  type JobColumn,
  type WorkspaceJob,
} from "../lib/workspace";
import { EditableCell } from "./EditableCell";

const TITLE_COLUMN: JobColumn = {
  id: "job_title",
  label: "Job Name",
  kind: "text",
};

type JobSummaryTableProps = {
  jobs: WorkspaceJob[];
  activeJobId: string | null;
  runsById: Record<string, RunDetail>;
  parameterColumns: JobColumn[];
  showDifferentOnly: boolean;
  onToggleShowDifferentOnly: (value: boolean) => void;
  onSelectJob: (jobId: string) => void;
  onUpdateJobTitle: (jobId: string, title: string) => void;
  onUpdateJobParameter: (jobId: string, column: JobColumn, value: unknown) => void;
  onTogglePlot: (jobId: string, enabled: boolean) => void;
  onDuplicateJob: (jobId: string) => void;
  onDeleteJob: (jobId: string) => void;
};

export function JobSummaryTable(props: JobSummaryTableProps) {
  const {
    jobs,
    activeJobId,
    runsById,
    parameterColumns,
    showDifferentOnly,
    onToggleShowDifferentOnly,
    onSelectJob,
    onUpdateJobTitle,
    onUpdateJobParameter,
    onTogglePlot,
    onDuplicateJob,
    onDeleteJob,
  } = props;

  const baselineJob = jobs.find((job) => job.id === activeJobId) ?? jobs[0] ?? null;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Job Matrix</p>
          <h2>Editable Summary Table</h2>
        </div>
        <label className="toggle-pill">
          <input
            type="checkbox"
            checked={showDifferentOnly}
            onChange={(event) => onToggleShowDifferentOnly(event.target.checked)}
          />
          <span>Only differing columns</span>
        </label>
      </div>

      <p className="summary-note">
        Rows are jobs. Columns are parameters. The active tab is the baseline for diff highlighting.
      </p>

      <div className="table-scroll">
        <table className="summary-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Plot</th>
              <th>State</th>
              <th>Last Run</th>
              <th>Actions</th>
              {parameterColumns.map((column) => (
                <th key={column.id}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const run = job.lastRunId ? runsById[job.lastRunId] : undefined;
              return (
                <tr
                  key={job.id}
                  data-testid={`job-row-${job.id}`}
                  className={job.id === activeJobId ? "summary-row-active" : ""}
                  onClick={() => onSelectJob(job.id)}
                >
                  <td className="sticky-column">
                    <EditableCell
                      jobLabel={job.title}
                      column={TITLE_COLUMN}
                      value={job.title}
                      onCommit={(value) => onUpdateJobTitle(job.id, String(value ?? ""))}
                    />
                  </td>
                  <td onClick={(event) => event.stopPropagation()}>
                    <input
                      aria-label={`${job.title} plot`}
                      className="cell-checkbox"
                      type="checkbox"
                      checked={job.plotEnabled}
                      onChange={(event) => onTogglePlot(job.id, event.target.checked)}
                    />
                  </td>
                  <td>
                    <span className={`status-pill status-${run?.state ?? "queued"}`}>{run?.state ?? "draft"}</span>
                  </td>
                  <td className="cell-readonly">
                    <div>{shortRunId(job.lastRunId)}</div>
                    {run?.updated_at ? <small>{new Date(run.updated_at).toLocaleTimeString()}</small> : null}
                  </td>
                  <td onClick={(event) => event.stopPropagation()}>
                    <div className="row-actions">
                      <button type="button" className="ghost-button row-action-button" onClick={() => onDuplicateJob(job.id)}>
                        Duplicate
                      </button>
                      <button type="button" className="ghost-button row-action-button" onClick={() => onDeleteJob(job.id)}>
                        Delete
                      </button>
                    </div>
                  </td>
                  {parameterColumns.map((column) => {
                    const value = column.path ? getValue(job, column.path) : null;
                    const differs = columnValueDiffers(column, job, baselineJob);
                    return (
                      <td
                        key={`${job.id}-${column.id}`}
                        className={differs ? "summary-cell-diff" : ""}
                        data-testid={`cell-${job.id}-${column.id}`}
                        onClick={(event) => event.stopPropagation()}
                      >
                        <EditableCell
                          jobLabel={`${job.title} ${formatLabel(column.id)}`}
                          column={column}
                          value={value}
                          onCommit={(nextValue) => onUpdateJobParameter(job.id, column, nextValue)}
                        />
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function getValue(job: WorkspaceJob, path: string): unknown {
  return path.split(".").reduce<unknown>((current, segment) => {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    return (current as Record<string, unknown>)[segment];
  }, job.config);
}
