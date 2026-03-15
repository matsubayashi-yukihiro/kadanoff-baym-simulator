import type { RunDetail } from "../api/types";
import { formatDateTime, formatLabel, formatValue } from "../lib/format";

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
            <p className="eyebrow">Diagnostics</p>
            <h2>DiagnosticsPanel</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>No diagnostics loaded.</p>
          <p>Select a run to inspect solver outputs and stability metrics.</p>
        </div>
      </section>
    );
  }

  const diagnostics = run.diagnostics && Object.keys(run.diagnostics).length > 0 ? run.diagnostics : run.diagnostics_excerpt ?? {};
  const diagnosticEntries = Object.entries(diagnostics);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Diagnostics</p>
          <h2>DiagnosticsPanel</h2>
        </div>
        <span className={`status-pill status-${run.state}`}>{run.state}</span>
      </div>

      <div className="diagnostic-summary">
        <div>
          <span className="focus-key">Run ID</span>
          <span>{run.run_id}</span>
        </div>
        <div>
          <span className="focus-key">Updated</span>
          <span>{formatDateTime(run.updated_at)}</span>
        </div>
        <div>
          <span className="focus-key">Lattice</span>
          <span>
            {formatValue(run.lattice.nx)} x {formatValue(run.lattice.ny)}
          </span>
        </div>
        <div>
          <span className="focus-key">Time Step</span>
          <span>{formatValue(run.time_grid.dt)}</span>
        </div>
      </div>

      {diagnosticEntries.length === 0 ? (
        <div className="empty-card">
          <p>No diagnostics stored yet.</p>
          <p>Queued and running jobs will populate this panel when results land.</p>
        </div>
      ) : (
        <div className="metric-grid">
          {diagnosticEntries.map(([key, value]) => (
            <div key={key} className="metric-card">
              <span className="metric-label">{formatLabel(key)}</span>
              <span className="metric-value">{formatValue(value)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
