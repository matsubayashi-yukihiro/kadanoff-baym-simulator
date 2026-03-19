import type { RunDetail, SimulationConfigInput } from "../api/types";
import { formatDateTime } from "../lib/format";
import { getSimulationTrack, TRACK_DESCRIPTORS, VALIDATION_GUARDRAILS } from "../lib/projectNarrative";

type ValidationScopePanelProps = {
  draftConfig: SimulationConfigInput;
  selectedRun: RunDetail | null;
};

export function ValidationScopePanel(props: ValidationScopePanelProps) {
  const { draftConfig, selectedRun } = props;
  const draftTrack = getSimulationTrack(draftConfig);
  const selectedTrack = selectedRun ? getSimulationTrack(selectedRun.config) : null;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Validation Scope</p>
          <h2>Solver Ladder And Claim Boundary</h2>
        </div>
      </div>

      <div className="context-grid">
        <article className={`context-card context-card-${draftTrack.tone}`}>
          <span className="briefing-label">Draft Target</span>
          <h3>{draftTrack.title}</h3>
          <div className="track-badge-row">
            <span className={`validation-pill validation-${draftTrack.tone}`}>{draftTrack.statusLabel}</span>
            <span className="signal-badge">Draft</span>
          </div>
          <p>{draftTrack.scope}</p>
        </article>

        <article className={`context-card ${selectedTrack ? `context-card-${selectedTrack.tone}` : ""}`}>
          <span className="briefing-label">Selected Artifact</span>
          <h3>{selectedRun?.name ?? selectedRun?.run_id ?? "No run selected"}</h3>
          {selectedTrack ? (
            <div className="track-badge-row">
              <span className={`validation-pill validation-${selectedTrack.tone}`}>{selectedTrack.statusLabel}</span>
              <span className="signal-badge signal-badge-strong">{selectedRun?.state ?? "queued"}</span>
            </div>
          ) : null}
          <p>{selectedTrack ? selectedTrack.scope : "Select a stored run to compare the artifact against the documented solver ladder."}</p>
          {selectedRun ? <p className="field-hint">Updated {formatDateTime(selectedRun.updated_at)}</p> : null}
        </article>
      </div>

      <details className="validation-details">
        <summary className="validation-details-summary">
          <span className="validation-details-text">
            <span className="briefing-label">Solver Ladder</span>
            <span className="validation-details-copy">Open the full validation ladder and guardrails when you need claim-boundary detail.</span>
          </span>
          <span className="signal-badge">Show details</span>
        </summary>

        <div className="validation-details-body">
          <div className="track-grid">
            {TRACK_DESCRIPTORS.map((track) => {
              const isDraft = track.key === draftTrack.key;
              const isSelected = track.key === selectedTrack?.key;
              const stateClassName = `track-card track-card-${track.tone}${isDraft || isSelected ? " track-card-active" : ""}`;

              return (
                <article key={track.key} className={stateClassName}>
                  <div className="track-header">
                    <div>
                      <h3>{track.title}</h3>
                    </div>
                    <div className="track-badge-row">
                      <span className={`validation-pill validation-${track.tone}`}>{track.statusLabel}</span>
                      {isDraft ? <span className="signal-badge">Draft</span> : null}
                      {isSelected ? <span className="signal-badge signal-badge-strong">Selected run</span> : null}
                    </div>
                  </div>
                  <p>{track.scope}</p>
                  <p className="track-evidence">{track.evidence}</p>
                  {track.caution ? <p className="track-caution">{track.caution}</p> : null}
                </article>
              );
            })}
          </div>

          <div className="panel-subheader">
            <h3>Guardrails</h3>
          </div>

          <div className="note-grid">
            {VALIDATION_GUARDRAILS.map((item) => (
              <article key={item.title} className="note-card">
                <span className="briefing-label">{item.title}</span>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
