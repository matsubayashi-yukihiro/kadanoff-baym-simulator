import type { RunDetail } from "../api/types";
import type { UseResearchArtifactsReturn } from "../hooks/useResearchArtifacts";
import type { WorkbenchTab } from "../lib/workbench";

const NOTE_KINDS = ["observation", "failure", "decision", "todo"] as const;

type ResearchArtifactsPanelProps = {
  activeTab: WorkbenchTab;
  run: RunDetail | null;
  selectedObservable: string | null;
  artifacts: UseResearchArtifactsReturn;
};

export function ResearchArtifactsPanel(props: ResearchArtifactsPanelProps) {
  const { activeTab, run, artifacts } = props;
  const {
    studies,
    linkedStudy,
    notes,
    notesLoading,
    bundles,
    noteForm,
    setNoteForm,
    isSubmittingNote,
    noteSubmitError,
    submitNote,
    studyForm,
    setStudyForm,
    isSubmittingStudy,
    studySubmitError,
    submitStudy,
    isLinkingStudy,
    linkStudyError,
    linkRunToStudy,
  } = artifacts;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Research Artifacts</p>
          <h2>Notes, Analysis, And Bundles</h2>
        </div>
      </div>

      {/* Linked Study */}
      <article className="note-card">
        <span className="briefing-label">Active Study</span>
        {linkedStudy ? (
          <>
            <p>
              <strong>{linkedStudy.title}</strong>
            </p>
            <p className="field-hint">{linkedStudy.question}</p>
            <span className="signal-badge">{linkedStudy.status}</span>
          </>
        ) : (
          <>
            <p className="field-hint">No study linked to this run.</p>
            {run && studies.length > 0 ? (
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                <select
                  style={{ flex: 1, minWidth: 0 }}
                  defaultValue=""
                  onChange={(e) => {
                    if (e.target.value) void linkRunToStudy(e.target.value);
                  }}
                  disabled={isLinkingStudy}
                >
                  <option value="">— link a study —</option>
                  {studies.map((s) => (
                    <option key={s.study_id} value={s.study_id}>
                      {s.title}
                    </option>
                  ))}
                </select>
                {isLinkingStudy && <span className="field-hint">Linking…</span>}
              </div>
            ) : run ? (
              <p className="field-hint">No studies yet. Create one below.</p>
            ) : (
              <p className="field-hint">Select a run to link a study.</p>
            )}
            {linkStudyError && <p className="field-hint">{linkStudyError}</p>}
          </>
        )}
      </article>

      {/* Decision Notes for this run */}
      <article className="note-card">
        <span className="briefing-label">Run Notes</span>
        {!run ? (
          <p className="field-hint">Select a run to see its notes.</p>
        ) : notesLoading ? (
          <p className="field-hint">Loading notes…</p>
        ) : notes.length === 0 ? (
          <p className="field-hint">No notes for this run yet.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {notes.map((note) => (
              <div key={note.note_id} style={{ borderLeft: "2px solid var(--color-border)", paddingLeft: "0.5rem" }}>
                <span className="signal-badge">{note.note_kind}</span>
                <p style={{ margin: "0.25rem 0 0" }}>{note.body}</p>
                <p className="field-hint">{new Date(note.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        )}
      </article>

      {/* Add Note */}
      <article className="note-card">
        <span className="briefing-label">Add Note</span>
        {!linkedStudy ? (
          <p className="field-hint">Link a study first to create notes.</p>
        ) : (
          <>
            <select
              value={noteForm.kind}
              onChange={(e) =>
                setNoteForm({ ...noteForm, kind: e.target.value as typeof noteForm.kind })
              }
              disabled={isSubmittingNote}
              style={{ marginBottom: "0.5rem", width: "100%" }}
            >
              {NOTE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
            <textarea
              value={noteForm.body}
              onChange={(e) => setNoteForm({ ...noteForm, body: e.target.value })}
              rows={3}
              placeholder="Write your observation, decision, or note…"
              disabled={isSubmittingNote}
              style={{ width: "100%", resize: "vertical", marginBottom: "0.5rem", boxSizing: "border-box" }}
            />
            <button
              className="action-button"
              onClick={() => void submitNote()}
              disabled={isSubmittingNote || !noteForm.body.trim()}
            >
              {isSubmittingNote ? "Saving…" : "Save Note"}
            </button>
            {noteSubmitError && <p className="field-hint">{noteSubmitError}</p>}
          </>
        )}
      </article>

      {/* Disclosure: Study management + evidence bundles */}
      <details className="support-details">
        <summary className="support-details-summary">
          <span className="support-details-text">
            <span className="briefing-label">Study Management &amp; Evidence Bundles</span>
            <span className="support-details-copy">Create studies and browse evidence bundles.</span>
          </span>
          <span className="signal-badge">Show</span>
        </summary>

        <div className="support-details-body">
          <div className="note-grid note-grid-1">
            {/* Create Study */}
            <article className="note-card">
              <span className="briefing-label">Create Study</span>
              <input
                type="text"
                placeholder="Study title"
                value={studyForm.title}
                onChange={(e) => setStudyForm({ ...studyForm, title: e.target.value })}
                disabled={isSubmittingStudy}
                style={{ width: "100%", marginBottom: "0.5rem", boxSizing: "border-box" }}
              />
              <textarea
                placeholder="Research question"
                value={studyForm.question}
                onChange={(e) => setStudyForm({ ...studyForm, question: e.target.value })}
                rows={2}
                disabled={isSubmittingStudy}
                style={{ width: "100%", resize: "vertical", marginBottom: "0.5rem", boxSizing: "border-box" }}
              />
              <button
                className="action-button"
                onClick={() => void submitStudy()}
                disabled={isSubmittingStudy || !studyForm.title.trim() || !studyForm.question.trim()}
              >
                {isSubmittingStudy ? "Creating…" : "Create Study"}
              </button>
              {studySubmitError && <p className="field-hint">{studySubmitError}</p>}
            </article>

            {/* Evidence Bundles (read-only) */}
            <article className="note-card">
              <span className="briefing-label">Evidence Bundles</span>
              {!linkedStudy ? (
                <p className="field-hint">Link a study to browse its evidence bundles.</p>
              ) : bundles.length === 0 ? (
                <p className="field-hint">No bundles for this study yet.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {bundles.map((b) => (
                    <div key={b.bundle_id}>
                      <strong>{b.title}</strong>
                      <p className="field-hint">{b.claim_candidate}</p>
                    </div>
                  ))}
                </div>
              )}
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
