import type { PresetConfig, RunDetail, SimulationConfigInput } from "../api/types";
import { analyzeFailure } from "../lib/failureAnalysis";
import { formatDateTime, formatLabel } from "../lib/format";
import { getSimulationTrack } from "../lib/projectNarrative";
import { summarizeBaselineRelation } from "../lib/workbench";

type RunContextPanelProps = {
  run: RunDetail | null;
  baselinePreset: PresetConfig | SimulationConfigInput;
  evidenceSurface: string;
};

export function RunContextPanel(props: RunContextPanelProps) {
  const { run, baselinePreset, evidenceSurface } = props;

  if (!run) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Run Framing</p>
            <h2>Baseline And Failure Context</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>No run selected.</p>
          <p>Select a stored artifact to frame it against the working baseline scaffold.</p>
        </div>
      </section>
    );
  }

  const track = getSimulationTrack(run.config);
  const relation = summarizeBaselineRelation(run.config, baselinePreset);
  const failureTags = getFailureTags(run.state);
  const provisionalJudgment = run.state === "succeeded" ? "screening" : "unchecked";
  const failure = analyzeFailure(run);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Run Framing</p>
          <h2>Baseline And Failure Context</h2>
        </div>
        <span className={`status-pill status-${run.state}`}>{run.state}</span>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span className="metric-label">Suggested Role</span>
          <span className="metric-value">{formatLabel(relation.suggestedRole)}</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Study Judgment</span>
          <span className="metric-value">{provisionalJudgment}</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Validation Scope</span>
          <span className="metric-value">{track.statusLabel}</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Failure Tags</span>
          <span className="metric-value">{failureTags.length > 0 ? failureTags.join(", ") : "none"}</span>
        </article>
      </div>

      <div className="panel-subheader">
        <h3>Working Baseline Relation</h3>
      </div>

      <div className="grid gap-3">
        <article
          className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px]"
          style={{
            padding: "0.85rem 0.95rem",
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
          }}
        >
          <p className="m-0 text-ink-subtle">{relation.summary}</p>
        </article>
        {relation.differences.map((item) => (
          <article
            key={item}
            className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px]"
            style={{
              padding: "0.85rem 0.95rem",
              background:
                "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
            }}
          >
            <p className="m-0 text-ink-subtle">{item}</p>
          </article>
        ))}
      </div>

      {track.caution ? <p className="state-banner state-error">{track.caution}</p> : null}

      {failure ? (
        <>
          <div className="panel-subheader">
            <h3>Failure Analysis</h3>
          </div>
          <div className="failure-analysis">
            <div className="failure-header">
              <span className={`failure-category failure-category-${failure.category}`}>{formatLabel(failure.category)}</span>
            </div>
            <p className="failure-summary">{failure.summary}</p>
            {failure.details.length > 0 ? (
              <ul className="failure-details">
                {failure.details.map((detail, index) => (
                  <li key={index}>{detail}</li>
                ))}
              </ul>
            ) : null}
            <p className="failure-action">{failure.suggestedAction}</p>
          </div>
        </>
      ) : null}

      <div className="panel-subheader">
        <h3>Artifact Reading</h3>
      </div>

      <div className="grid gap-3.5 grid-cols-[repeat(2,minmax(0,1fr))]">
        <article
          className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px] p-3.5"
          style={{
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
          }}
        >
          <span className="briefing-label">Evidence Surface</span>
          <p className="m-0 text-ink-subtle">{evidenceSurface}</p>
        </article>
        <article
          className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px] p-3.5"
          style={{
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
          }}
        >
          <span className="briefing-label">Status Message</span>
          <p className="m-0 text-ink-subtle">{run.status_message ?? "No status message recorded."}</p>
        </article>
        <article
          className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px] p-3.5"
          style={{
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
          }}
        >
          <span className="briefing-label">Updated</span>
          <p className="m-0 text-ink-subtle">{formatDateTime(run.updated_at)}</p>
        </article>
        <article
          className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px] p-3.5"
          style={{
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
          }}
        >
          <span className="briefing-label">Research Metadata</span>
          <p className="m-0 text-ink-subtle">Durable run_role, validation_status, and failure_tags will move to registry-backed metadata once P1.5 lands.</p>
        </article>
      </div>
    </section>
  );
}

function getFailureTags(state: RunDetail["state"]): string[] {
  if (state === "failed") {
    return ["solver_failed"];
  }
  if (state === "cancelled") {
    return ["cancelled"];
  }
  return [];
}
