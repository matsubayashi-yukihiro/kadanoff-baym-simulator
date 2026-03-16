import type { RunDetail } from "../api/types";
import type { WorkspaceJob } from "../lib/workspace";

type JobTabsBarProps = {
  jobs: WorkspaceJob[];
  activeJobId: string | null;
  runsById: Record<string, RunDetail>;
  onCreateJob: () => void;
  onSelectJob: (jobId: string) => void;
};

export function JobTabsBar(props: JobTabsBarProps) {
  const { jobs, activeJobId, runsById, onCreateJob, onSelectJob } = props;

  return (
    <section className="panel tabs-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h2>Job Tabs</h2>
        </div>
        <button type="button" className="primary-button" onClick={onCreateJob}>
          New Draft
        </button>
      </div>

      <div className="tab-strip" role="tablist" aria-label="Job tabs">
        {jobs.map((job) => {
          const run = job.lastRunId ? runsById[job.lastRunId] : undefined;
          return (
            <button
              key={job.id}
              type="button"
              role="tab"
              aria-selected={job.id === activeJobId}
              className={`tab-button ${job.id === activeJobId ? "tab-button-active" : ""}`}
              onClick={() => onSelectJob(job.id)}
            >
              <span className="tab-kicker">{job.id === activeJobId ? "Active Draft" : "Draft"}</span>
              <span className="tab-title">{job.title}</span>
              <span className="tab-caption">{job.config.solver}</span>
              <span className="tab-meta">
                <span className={`status-pill status-${run?.state ?? "queued"}`}>{run?.state ?? "draft"}</span>
                {job.plotEnabled ? <span className="tab-plot-flag">plot</span> : null}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
