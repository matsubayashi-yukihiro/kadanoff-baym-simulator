import type { PresetConfig, SimulationConfigInput } from "../api/types";
import { describeComparisonDraft } from "../lib/workbench";

type CompareJobsRailPanelProps = {
  draftConfig: SimulationConfigInput;
  baselinePreset: PresetConfig | SimulationConfigInput;
  baselinePresetName: string | null;
};

export function CompareJobsRailPanel(props: CompareJobsRailPanelProps) {
  const { draftConfig, baselinePreset, baselinePresetName } = props;
  const summary = describeComparisonDraft(draftConfig, baselinePreset, baselinePresetName);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Compare Framing</p>
          <h2>Variant Rail</h2>
        </div>
        <span className="signal-badge">{summary.comparisonKindLabel}</span>
      </div>

      <p className="state-banner state-warning">{summary.comparisonKindReason}</p>

      <div className="sidebar-stack">
        <article className="sidebar-card">
          <span className="sidebar-card-label">Comparison Kind</span>
          <strong className="sidebar-card-value">{summary.comparisonKind}</strong>
          <p className="sidebar-card-copy">Keep the future compare artifact explicit about whether it is hypothesis-facing or numerical validation work.</p>
        </article>
        <article className="sidebar-card">
          <span className="sidebar-card-label">Baseline</span>
          <strong className="sidebar-card-value">{summary.baselineName}</strong>
          <p className="sidebar-card-copy">Anchor every variant list to one stated baseline before overlay or difference plots enter the page.</p>
        </article>
        <article className="sidebar-card">
          <span className="sidebar-card-label">Variant Intent</span>
          <strong className="sidebar-card-value">{summary.templateSeed}</strong>
          <p className="sidebar-card-copy">{summary.variantIntent}</p>
        </article>
      </div>

      <div className="panel-subheader">
        <h3>Variant Slots</h3>
      </div>

      <div className="compare-variant-list">
        {summary.variants.map((variant) => (
          <article
            key={variant.key}
            className={`compare-variant-card ${variant.active ? "compare-variant-card-active" : ""} ${
              variant.planning ? "compare-variant-card-planning" : ""
            }`}
          >
            <div className="compare-variant-header">
              <div>
                <span className="compare-variant-slot">{variant.slot}</span>
                <h3>{variant.label}</h3>
              </div>
              <div className="compare-variant-badges">
                {variant.badges.map((badge) => (
                  <span key={badge} className="signal-badge">
                    {badge}
                  </span>
                ))}
              </div>
            </div>

            <p className="compare-variant-summary">{variant.summary}</p>
            <p className="field-hint">{variant.detail}</p>

            {variant.differences.length > 0 ? (
              <div className="compare-variant-differences">
                {variant.differences.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>

      <div className="panel-subheader">
        <h3>Guardrails</h3>
      </div>

      <div className="stack-list">
        {summary.guardrails.map((item) => (
          <article key={item} className="stack-item">
            <p>{item}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
