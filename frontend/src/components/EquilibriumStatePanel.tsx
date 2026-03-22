import type { RunDetail } from "../api/types";
import { formatNumber, formatValue } from "../lib/format";

type EquilibriumStatePanelProps = {
  run: RunDetail | null;
};

export function EquilibriumStatePanel(props: EquilibriumStatePanelProps) {
  const { run } = props;

  if (!run) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Ground State</p>
            <h2>Equilibrium State</h2>
          </div>
        </div>
        <div className="empty-card">
          <p>No run selected.</p>
          <p>Select a completed tdhfb or kbe_hfb run to inspect the equilibrium solution.</p>
        </div>
      </section>
    );
  }

  // Only tdhfb / kbe_hfb have an HFB equilibrium step
  if (run.solver === "noninteracting") {
    return null;
  }

  const diag = (run.diagnostics && Object.keys(run.diagnostics).length > 0
    ? run.diagnostics
    : run.diagnostics_excerpt ?? {}) as Record<string, unknown>;

  const converged = diag["hfb_converged"] as boolean | undefined;
  const iterations = diag["hfb_iterations"] as number | undefined;
  const selfConsistencyError = diag["hfb_self_consistency_error"] as number | undefined;
  const stationarityResidual = diag["equilibrium_stationarity_residual"] as number | undefined;
  const chemicalPotential = diag["effective_chemical_potential"] as number | undefined;
  const equilibriumDensity = diag["equilibrium_density"] as number | undefined;
  const equilibriumEnergy = diag["equilibrium_energy"] as number | undefined;
  const equilibriumPairing = diag["equilibrium_pairing"] as number | undefined;
  const equilibriumPairingS = diag["equilibrium_pairing_s"] as number | undefined;
  const equilibriumPairingD = diag["equilibrium_pairing_d"] as number | undefined;

  const hasEquilibriumData =
    converged !== undefined ||
    equilibriumDensity !== undefined ||
    equilibriumPairing !== undefined;

  if (!hasEquilibriumData && run.state !== "succeeded") {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Ground State</p>
            <h2>Equilibrium State</h2>
          </div>
          <span className={`status-pill status-${run.state}`}>{run.state}</span>
        </div>
        <p className="state-banner">Equilibrium results will appear after the run completes.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Ground State</p>
          <h2>Equilibrium State</h2>
        </div>
        <span className={`status-pill status-${run.state}`}>{run.state}</span>
      </div>

      {converged === false ? (
        <p className="state-banner state-warning">
          HFB did not converge — equilibrium values may be unreliable.
        </p>
      ) : converged === true ? (
        <p className="state-banner state-nominal">HFB converged.</p>
      ) : null}

      {/* Convergence block */}
      {(converged !== undefined || iterations !== undefined || selfConsistencyError !== undefined || stationarityResidual !== undefined) ? (
        <div className="metric-grid">
          {converged !== undefined ? (
            <div className={`metric-card ${converged ? "" : "metric-card-anomalous"}`}>
              <span className="metric-label">Converged</span>
              <span className="metric-value">{formatValue(converged)}</span>
            </div>
          ) : null}
          {iterations !== undefined ? (
            <div className="metric-card">
              <span className="metric-label">Iterations</span>
              <span className="metric-value">{iterations}</span>
            </div>
          ) : null}
          {selfConsistencyError !== undefined ? (
            <div className="metric-card">
              <span className="metric-label">Self-consistency error</span>
              <span className="metric-value">{formatNumber(selfConsistencyError, 4)}</span>
            </div>
          ) : null}
          {stationarityResidual !== undefined ? (
            <div className="metric-card">
              <span className="metric-label">Stationarity residual</span>
              <span className="metric-value">{formatNumber(stationarityResidual, 4)}</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Equilibrium observables block */}
      {(chemicalPotential !== undefined || equilibriumDensity !== undefined || equilibriumEnergy !== undefined) ? (
        <>
          <div className="panel-subheader">
            <h3>Converged values (t = 0)</h3>
          </div>
          <div className="metric-grid">
            {chemicalPotential !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">μ (effective)</span>
                <span className="metric-value">{formatNumber(chemicalPotential, 4)}</span>
              </div>
            ) : null}
            {equilibriumDensity !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">n(0)</span>
                <span className="metric-value">{formatNumber(equilibriumDensity, 4)}</span>
              </div>
            ) : null}
            {equilibriumEnergy !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">E(0)</span>
                <span className="metric-value">{formatNumber(equilibriumEnergy, 4)}</span>
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      {/* Order parameter block */}
      {(equilibriumPairing !== undefined || equilibriumPairingS !== undefined || equilibriumPairingD !== undefined) ? (
        <>
          <div className="panel-subheader">
            <h3>Order parameters (t = 0)</h3>
          </div>
          <div className="metric-grid">
            {equilibriumPairing !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">|Δ(0)|</span>
                <span className="metric-value">{formatNumber(equilibriumPairing, 5)}</span>
              </div>
            ) : null}
            {equilibriumPairingS !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">|Δ_s(0)|</span>
                <span className="metric-value">{formatNumber(equilibriumPairingS, 5)}</span>
              </div>
            ) : null}
            {equilibriumPairingD !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">|Δ_d(0)|</span>
                <span className="metric-value">{formatNumber(equilibriumPairingD, 5)}</span>
              </div>
            ) : null}
            {/* Derived: superconducting gap 2|Δ| */}
            {equilibriumPairing !== undefined ? (
              <div className="metric-card">
                <span className="metric-label">2|Δ| (gap)</span>
                <span className="metric-value">{formatNumber(2 * equilibriumPairing, 5)}</span>
              </div>
            ) : null}
            {/* Derived: condensation fraction |Δ|/n */}
            {equilibriumPairing !== undefined && equilibriumDensity !== undefined && equilibriumDensity > 0 ? (
              <div className="metric-card">
                <span className="metric-label">|Δ|/n</span>
                <span className="metric-value">{formatNumber(equilibriumPairing / equilibriumDensity, 4)}</span>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
