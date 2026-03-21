import type { PresetEntry } from "../api/types";
import { describePreset } from "../lib/workbench";
import { CollapsibleSection } from "./ui/CollapsibleSection";

const CATEGORY_LABELS: Record<string, string> = {
  demo: "Demo",
  working_baseline: "Working baseline",
  mean_field: "Mean-field",
  exact_baseline: "Exact baseline",
};

const VALIDATION_LABELS: Record<string, string> = {
  validated: "Validated",
  partial: "Partial",
  prototype: "Prototype",
};

const VALIDATION_PILL_TONE: Record<string, string> = {
  validated: "validation-validated",
  partial: "validation-partial",
  prototype: "validation-prototype",
};

type PresetLibraryPanelProps = {
  presets: PresetEntry[];
  loading: boolean;
  error: string | null;
  activePresetName: string | null;
  workingBaselineName: string | null;
  showHiggsQuickstart: boolean;
  higgsDemoName: string | null;
  busy: boolean;
  onLoadPreset: (preset: PresetEntry) => void;
  onStageHiggsDemo: () => void;
  onLaunchHiggsDemo: () => Promise<void> | void;
};

export function PresetLibraryPanel(props: PresetLibraryPanelProps) {
  const {
    presets,
    loading,
    error,
    activePresetName,
    workingBaselineName,
    showHiggsQuickstart,
    higgsDemoName,
    busy,
    onLoadPreset,
    onStageHiggsDemo,
    onLaunchHiggsDemo,
  } = props;
  const higgsDemoActive = activePresetName === higgsDemoName;
  const higgsPreset = presets.find((p) => p.name === higgsDemoName);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Preset</p>
          <h2>Preset Library</h2>
        </div>
      </div>

      {showHiggsQuickstart ? (
        <article className={`preset-quickstart-card ${higgsDemoActive ? "preset-card-active" : ""}`}>
          <div className="panel-subheader">
            <h3>Higgs Demo Quick Start</h3>
            <div className="hero-badge-row">
              <span className="signal-badge">Demo preset</span>
              <span className="signal-badge">Single Job</span>
              {higgsPreset && (
                <span className={`validation-pill ${VALIDATION_PILL_TONE[higgsPreset.validation_status] ?? "validation-partial"}`}>
                  {VALIDATION_LABELS[higgsPreset.validation_status] ?? higgsPreset.validation_status}
                </span>
              )}
            </div>
          </div>
          <p>{higgsPreset?.summary ?? "kbe_hfb + hfb + bond_d run with Gaussian pulse."}</p>
          <p className="field-hint">{higgsPreset?.scope_note ?? "Demo values — provisional."}</p>
          <div className="button-row">
            <button type="button" className="ghost-button" onClick={onStageHiggsDemo} disabled={busy}>
              Stage Demo
            </button>
            <button type="button" className="primary-button" onClick={onLaunchHiggsDemo} disabled={busy}>
              Launch Demo
            </button>
          </div>
        </article>
      ) : null}

      {loading ? <p className="state-banner">Loading presets...</p> : null}
      {error ? <p className="state-banner state-error">{error}</p> : null}
      {!loading && presets.length === 0 ? (
        <div className="empty-card">
          <p>No presets available.</p>
          <p>The draft remains editable without preset metadata.</p>
        </div>
      ) : null}

      <CollapsibleSection title={`All presets (${presets.length})`} defaultOpen={false}>
        <div className="preset-list">
          {presets.map((preset) => {
            const isActive = preset.name === activePresetName;
            const isBaseline = preset.name === workingBaselineName;
            const categoryLabel = CATEGORY_LABELS[preset.category] ?? preset.category;
            const validationTone = VALIDATION_PILL_TONE[preset.validation_status] ?? "validation-partial";
            const validationLabel = VALIDATION_LABELS[preset.validation_status] ?? preset.validation_status;

            return (
              <article key={preset.name} className={`preset-card ${isActive ? "preset-card-active" : ""}`}>
                <div className="panel-subheader">
                  <h3>{preset.name}</h3>
                  <div className="hero-badge-row">
                    <span className="signal-badge">{categoryLabel}</span>
                    <span className={`validation-pill ${validationTone}`}>{validationLabel}</span>
                    {isBaseline ? <span className="signal-badge">Working baseline</span> : null}
                  </div>
                </div>
                <p>{preset.summary}</p>
                <p className="field-hint">{preset.scope_note}</p>
                <button type="button" className="ghost-button" onClick={() => onLoadPreset(preset)} aria-label={`Load ${describePreset(preset.config).title}`}>
                  Load preset
                </button>
              </article>
            );
          })}
        </div>
      </CollapsibleSection>
    </section>
  );
}
