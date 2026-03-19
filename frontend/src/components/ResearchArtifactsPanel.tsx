import type { RunDetail } from "../api/types";
import type { WorkbenchTab } from "../lib/workbench";

type ResearchArtifactsPanelProps = {
  activeTab: WorkbenchTab;
  run: RunDetail | null;
  selectedObservable: string | null;
};

export function ResearchArtifactsPanel(props: ResearchArtifactsPanelProps) {
  const { activeTab, run, selectedObservable } = props;
  const currentArtifactCopy = run
    ? `Reading ${selectedObservable ?? "observable"} on ${run.run_id}. Durable FFT, notes, and bundle lineage still depend on backend artifact resources.`
    : "Select a run before promoting local previews into research artifacts.";

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Research Artifacts</p>
          <h2>Notes, Analysis, And Bundles</h2>
        </div>
      </div>

      <article className="note-card">
        <span className="briefing-label">Current Artifact Surface</span>
        <p>{currentArtifactCopy}</p>
      </article>

      <details className="support-details">
        <summary className="support-details-summary">
          <span className="support-details-text">
            <span className="briefing-label">Artifact Backlog</span>
            <span className="support-details-copy">Derived analysis, decision notes, and evidence bundles still depend on registry-backed APIs.</span>
          </span>
          <span className="signal-badge">Show backlog</span>
        </summary>

        <div className="support-details-body">
          <div className="note-grid note-grid-1">
            <article className="note-card">
              <span className="briefing-label">Derived Analysis</span>
              <p>
                Persistent FFT and peak extraction should move out of local preview mode and into backend-derived
                analysis artifacts.
              </p>
            </article>
            <article className="note-card">
              <span className="briefing-label">Decision Note</span>
              <p>
                Capture `observation`, `failure`, `decision`, and `todo` as first-class artifacts once the
                `decision-notes` resource is available.
              </p>
            </article>
            <article className="note-card">
              <span className="briefing-label">Evidence Bundle</span>
              <p>
                Bundle runs, analyses, and validation scope without auto-promoting claims to validated status. This
                remains a future artifact API.
              </p>
            </article>
          </div>
        </div>
      </details>

      <p className="field-hint">
        Active surface: {activeTab}. Source artifact: {run?.run_id ?? "none"}.
      </p>
    </section>
  );
}
