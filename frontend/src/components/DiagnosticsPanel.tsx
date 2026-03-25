import type { RunDetail } from "../api/types";
import { countAnomalies, groupDiagnostics } from "../lib/diagnosticGroups";
import { analyzeFailure } from "../lib/failureAnalysis";
import { formatDateTime, formatLabel, formatValue } from "../lib/format";
import { getDiagnosticMeta } from "../lib/diagnosticMeta";

type DiagnosticsPanelProps = {
  run: RunDetail | null;
};

export function DiagnosticsPanel(props: DiagnosticsPanelProps) {
  const { run } = props;

  if (!run) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Baseline And Failure Context</p>
            <h2>Solver Diagnostics</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>No diagnostics loaded.</p>
          <p>Select a run to inspect solver outputs and stability metrics.</p>
        </div>
      </section>
    );
  }

  const failure = analyzeFailure(run);
  const diagnostics = run.diagnostics && Object.keys(run.diagnostics).length > 0 ? run.diagnostics : run.diagnostics_excerpt ?? {};
  const groups = groupDiagnostics(diagnostics as Record<string, unknown>);
  const isKSpaceRun = run.config?.representation === "k_space";
  const kSpacePathMode = typeof diagnostics["k_space_path_mode"] === "string" ? String(diagnostics["k_space_path_mode"]) : null;
  const kSpaceFallbackReason =
    typeof diagnostics["k_space_path_fallback_reason"] === "string"
      ? String(diagnostics["k_space_path_fallback_reason"])
      : null;
  const kSpaceInitialBlockError =
    typeof diagnostics["k_space_initial_block_structure_error"] === "number"
      ? Number(diagnostics["k_space_initial_block_structure_error"])
      : null;
  const secondBornKspaceBlockPath =
    typeof diagnostics["second_born_kspace_block_path"] === "boolean"
      ? Boolean(diagnostics["second_born_kspace_block_path"])
      : null;
  const secondBornSolverMode =
    typeof diagnostics["second_born_solver_mode"] === "string"
      ? String(diagnostics["second_born_solver_mode"])
      : null;
  const hasKSpacePathSignal =
    isKSpaceRun &&
    (kSpacePathMode !== null ||
      kSpaceFallbackReason !== null ||
      secondBornKspaceBlockPath !== null ||
      secondBornSolverMode !== null);
  const kSpaceFullFallback = kSpacePathMode === "full_matrix_fallback";
  const secondBornBlockInactive =
    run.solver === "kbe_hfb" &&
    run.config?.kbe?.self_energy === "second_born_reference" &&
    secondBornKspaceBlockPath === false;
  const kSpaceFallbackDetected = kSpaceFullFallback || secondBornBlockInactive;
  const anomalyCount = countAnomalies(groups);
  const entryCount = groups.reduce((sum, group) => sum + group.entries.length, 0);
  const anomalousEntries = groups
    .flatMap((group) =>
      group.entries
        .filter((entry) => entry.anomalous)
        .map((entry) => ({ groupLabel: group.label, key: entry.key, value: entry.value })),
    )
    .slice(0, 4);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Baseline And Failure Context</p>
          <h2>Solver Diagnostics</h2>
        </div>
        <span className={`status-pill status-${run.state}`}>{run.state}</span>
      </div>

      <div className="diagnostic-summary">
        <div>
          <span className="focus-key">Groups</span>
          <span>{groups.length}</span>
        </div>
        <div>
          <span className="focus-key">Updated</span>
          <span>{formatDateTime(run.updated_at)}</span>
        </div>
        <div>
          <span className="focus-key">Metrics</span>
          <span>{entryCount}</span>
        </div>
        <div>
          <span className="focus-key">Anomalies</span>
          <span>{anomalyCount}</span>
        </div>
      </div>

      {anomalyCount > 0 ? (
        <p className="state-banner state-warning">{anomalyCount} anomal{anomalyCount === 1 ? "y" : "ies"} detected in diagnostics.</p>
      ) : groups.length > 0 ? (
        <p className="state-banner state-nominal">All diagnostics nominal.</p>
      ) : null}

      {hasKSpacePathSignal ? (
        <>
          <div className="diagnostic-summary">
            <div>
              <span className="focus-key">k-space path mode</span>
              <span>{kSpacePathMode ?? "n/a"}</span>
            </div>
            <div>
              <span className="focus-key">fallback reason</span>
              <span>{kSpaceFallbackReason ?? "none"}</span>
            </div>
            <div>
              <span className="focus-key">2nd Born block path</span>
              <span>
                {secondBornKspaceBlockPath === null ? "n/a" : String(secondBornKspaceBlockPath)}
              </span>
            </div>
            <div>
              <span className="focus-key">initial block error</span>
              <span>{kSpaceInitialBlockError === null ? "n/a" : formatValue(kSpaceInitialBlockError)}</span>
            </div>
          </div>
          {kSpaceFallbackDetected ? (
            <p className="state-banner state-warning">
              k-space block path is inactive and fallback is in effect
              {kSpacePathMode ? ` (mode: ${kSpacePathMode})` : ""}
              {kSpaceFallbackReason ? `; reason: ${kSpaceFallbackReason}` : ""}.
            </p>
          ) : (
            <p className="state-banner state-nominal">k-space block path is active for this run.</p>
          )}
        </>
      ) : null}

      {failure ? (
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
      ) : null}

      {groups.length === 0 ? (
        <div className="empty-card">
          <p>No diagnostics stored yet.</p>
          <p>Queued and running jobs will populate this panel when results land.</p>
        </div>
      ) : (
        <>
          {anomalousEntries.length > 0 ? (
            <div className="grid gap-3">
              {anomalousEntries.map((entry) => {
                const meta = getDiagnosticMeta(entry.key);
                const tip = meta
                  ? meta.description + (meta.threshold ? `\n許容: ${meta.threshold}` : "")
                  : null;
                return (
                  <article
                    key={`${entry.groupLabel}-${entry.key}`}
                    className="grid gap-2 border border-panel-border rounded-panel shadow-card backdrop-blur-[14px] diagnostic-alert-item"
                    style={{
                      padding: "0.85rem 0.95rem",
                      background:
                        "linear-gradient(180deg, rgba(255,255,255,0.66), rgba(248,251,253,0.92)), var(--panel-bg)",
                    }}
                  >
                    <span className="briefing-label">{entry.groupLabel}</span>
                    <div className="flex items-center gap-1.5">
                      <p className="m-0">
                        {formatLabel(entry.key)} = {formatValue(entry.value)}
                      </p>
                      {tip ? <span className="help-tip" data-tip={tip} aria-label={meta!.description}>ⓘ</span> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}

          <details className="support-details">
            <summary className="support-details-summary">
              <span className="support-details-text">
                <span className="briefing-label">Full Diagnostic Matrix</span>
                <span className="support-details-copy">Open grouped solver metrics when you need the complete diagnostic surface.</span>
              </span>
              <span className="signal-badge">Show details</span>
            </summary>

            <div className="support-details-body">
              {groups.map((group) => (
                <div key={group.key}>
                  {groups.length > 1 ? (
                    <div className="panel-subheader">
                      <h3>{group.label}</h3>
                    </div>
                  ) : null}
                  <div className="metric-grid">
                    {group.entries.map((entry) => {
                      const meta = getDiagnosticMeta(entry.key);
                      const tip = meta
                        ? meta.description + (meta.threshold ? `\n許容: ${meta.threshold}` : "")
                        : null;
                      return (
                        <div key={entry.key} className={`metric-card ${entry.anomalous ? "metric-card-anomalous" : ""}`}>
                          <div className="flex items-center gap-1">
                            <span className="metric-label">{formatLabel(entry.key)}</span>
                            {tip ? <span className="help-tip" data-tip={tip} aria-label={meta!.description}>ⓘ</span> : null}
                          </div>
                          <span className="metric-value">{formatValue(entry.value)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </>
      )}
    </section>
  );
}
