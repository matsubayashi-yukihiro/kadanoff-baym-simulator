import { Sidebar } from "../components/layout/Sidebar";
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
    <>
      <Sidebar
        footer={
          <button type="button" className="primary-button w-full" disabled>
            Launch Sweep
          </button>
        }
      >
        <SweepRailPanel
          draftConfig={draftConfig}
          baselinePresetName={baselinePresetName}
        />

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

        <ConfigPanel
          config={draftConfig}
          disabled={isSubmitting || isCancelling}
          onConfigChange={setDraftConfig}
          onReset={resetDraft}
        />
      </Sidebar>

      <main className="flex-1 overflow-y-auto p-6 space-y-8">
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
    </>
  );
}
