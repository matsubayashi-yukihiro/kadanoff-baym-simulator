import type { PresetConfig, SimulationConfigInput } from "../api/types";
import { describeComparisonDraft } from "../lib/workbench";

type CompareJobsPlanningPanelProps = {
  draftConfig: SimulationConfigInput;
  baselinePreset: PresetConfig | SimulationConfigInput;
  baselinePresetName: string | null;
};

export function CompareJobsPlanningPanel(props: CompareJobsPlanningPanelProps) {
  const { draftConfig, baselinePreset, baselinePresetName } = props;
  const summary = describeComparisonDraft(draftConfig, baselinePreset, baselinePresetName);

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Comparison Summary</p>
            <h2>Read The Job Group Before The Plots</h2>
          </div>
          <span className="signal-badge">Summary first</span>
        </div>

        <p className={`state-banner ${summary.comparisonKind === "regression" ? "state-warning" : "state-nominal"}`}>
          {summary.planningBanner}
        </p>

        <div className="compare-summary-table-wrap">
          <table className="compare-summary-table">
            <tbody>
              {summary.summaryRows.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  <td>{row.code ? <code>{row.value}</code> : row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="compare-main-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Planning State</p>
              <h2>Child Runs And Artifact Status</h2>
            </div>
          </div>

          <div className="note-grid note-grid-2">
            {summary.planningSignals.map((signal) => (
              <article key={signal.title} className="note-card">
                <span className="briefing-label">{signal.title}</span>
                <strong>{signal.value}</strong>
                <p>{signal.copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Reserved Result Stack</p>
              <h2>Keep The Main Canvas Ordered</h2>
            </div>
          </div>

          <div className="stack-list">
            {summary.reservedViews.map((view) => (
              <article key={view.title} className="stack-item">
                <strong>{view.title}</strong>
                <p>{view.copy}</p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Empty State</p>
            <h2>{summary.emptyStateTitle}</h2>
          </div>
        </div>

        <div className="empty-card compare-empty-card">
          <p>{summary.emptyStateCopy}</p>
          <div className="compare-empty-steps">
            {summary.emptyStateSteps.map((step) => (
              <p key={step}>{step}</p>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
