import type { PresetConfig } from "../api/types";
import { describePreset } from "../lib/workbench";

type PresetLibraryPanelProps = {
  presets: PresetConfig[];
  loading: boolean;
  error: string | null;
  activePresetName: string | null;
  workingBaselineName: string | null;
  showHiggsQuickstart: boolean;
  higgsDemoName: string | null;
  busy: boolean;
  onLoadPreset: (preset: PresetConfig) => void;
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

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Preset</p>
          <h2>Preset Library</h2>
        </div>
      </div>

      <p className="field-hint">
        Current API presets are config-only. Category metadata and explicit demo/baseline separation will move to enriched presets later.
      </p>

      {showHiggsQuickstart ? (
        <article className={`preset-quickstart-card ${higgsDemoActive ? "preset-card-active" : ""}`}>
          <div className="panel-subheader">
            <h3>Higgs Demo Quick Start</h3>
            <div className="hero-badge-row">
              <span className="signal-badge">Demo preset</span>
              <span className="signal-badge">Single Job</span>
            </div>
          </div>
          <p>
            Stage or launch a provisional `kbe_hfb + hfb + bond_d` long-window Gaussian-pulse run with `pairing_d` as
            the primary readout.
          </p>
          <p className="field-hint">
            This is an illustrative demo path, not a validated baseline. The preset now reserves pre-pulse baseline and
            post-pulse FFT window, but the numbers remain editable draft values.
          </p>
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

      <div className="preset-list">
        {presets.map((preset) => {
          const descriptor = describePreset(preset);
          const isActive = preset.name === activePresetName;
          const isBaseline = preset.name === workingBaselineName;

          return (
            <article key={`${preset.name}-${preset.solver}`} className={`preset-card ${isActive ? "preset-card-active" : ""}`}>
              <div className="panel-subheader">
                <h3>{descriptor.title}</h3>
                <div className="hero-badge-row">
                  <span className="signal-badge">{descriptor.category}</span>
                  <span className="signal-badge">{descriptor.intendedTab}</span>
                  {isBaseline ? <span className="validation-pill validation-partial">Working baseline</span> : null}
                </div>
              </div>
              <p className="preset-name">{preset.name ?? "unnamed preset"}</p>
              <p>{descriptor.summary}</p>
              <p className="field-hint">{descriptor.scopeNote}</p>
              <button type="button" className="ghost-button" onClick={() => onLoadPreset(preset)}>
                Load {descriptor.title}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
