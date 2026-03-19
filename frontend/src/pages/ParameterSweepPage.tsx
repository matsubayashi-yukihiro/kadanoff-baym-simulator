import { SectionHeading } from "../components/ui/SectionHeading";
import { ConfigPanel } from "../components/ConfigPanel";
import { PresetLibraryPanel } from "../components/PresetLibraryPanel";
import { SweepRailPanel } from "../components/SweepRailPanel";
import { WorkbenchPlaceholderPanel } from "../components/WorkbenchPlaceholderPanel";
import { useConfigStore } from "../stores/useConfigStore";
import { useRunStore } from "../stores/useRunStore";
import {
  cloneConfig,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
  HIGGS_DEMO_PRIMARY_OBSERVABLE,
} from "../lib/workbench";

export function ParameterSweepPage() {
  const draftConfig = useConfigStore((s) => s.draftConfig);
  const setDraftConfig = useConfigStore((s) => s.setDraftConfig);
  const loadPreset = useConfigStore((s) => s.loadPreset);
  const resetDraft = useConfigStore((s) => s.resetDraft);
  const loadedPresetName = useConfigStore((s) => s.loadedPresetName);
  const setLoadedPresetName = useConfigStore((s) => s.setLoadedPresetName);
  const presets = useConfigStore((s) => s.presets);
  const presetsLoading = useConfigStore((s) => s.presetsLoading);
  const presetError = useConfigStore((s) => s.presetError);

  const isSubmitting = useRunStore((s) => s.isSubmitting);
  const isCancelling = useRunStore((s) => s.isCancelling);

  const baselinePreset = selectWorkingBaselinePreset(presets);
  const higgsDemoPreset = selectHiggsDemoPreset(presets);
  const baselinePresetName = baselinePreset.name ?? null;
  const higgsDemoName = higgsDemoPreset.name ?? null;

  function stagePreset(config: Parameters<typeof cloneConfig>[0]) {
    setDraftConfig(cloneConfig(config));
    setLoadedPresetName(config.name ?? null);
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">
      {/* 上段: パラメーター設定 */}
      <div className="p-6 border-b border-border-soft">
        <div className="params-grid">
          <div className="params-config-col">
            <ConfigPanel
              config={draftConfig}
              disabled={isSubmitting || isCancelling}
              onConfigChange={setDraftConfig}
              onReset={resetDraft}
            />
          </div>

          <PresetLibraryPanel
            presets={presets}
            loading={presetsLoading}
            error={presetError}
            activePresetName={loadedPresetName}
            workingBaselineName={baselinePresetName}
            showHiggsQuickstart={false}
            higgsDemoName={higgsDemoName}
            busy={isSubmitting || isCancelling}
            onLoadPreset={loadPreset}
            onStageHiggsDemo={() => stagePreset(higgsDemoPreset)}
            onLaunchHiggsDemo={() => stagePreset(higgsDemoPreset)}
          />

          <SweepRailPanel
            draftConfig={draftConfig}
            baselinePresetName={baselinePresetName}
          />
        </div>
      </div>

      {/* 下段: シミュレーション結果 */}
      <main className="flex-1 p-6 space-y-8">
        <section>
          <SectionHeading
            eyebrow="Sweep Planning"
            title="Design A Managed Sweep"
            copy="Use this page for scan setup and guardrails."
          />
          <WorkbenchPlaceholderPanel
            tab="parameter-sweep"
            draftConfig={draftConfig}
            baselinePresetName={baselinePresetName}
          />
        </section>
      </main>
    </div>
  );
}
