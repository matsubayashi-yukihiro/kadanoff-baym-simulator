import { Sidebar } from "../components/layout/Sidebar";
import { SectionHeading } from "../components/ui/SectionHeading";
import { CompareJobsPlanningPanel } from "../components/CompareJobsPlanningPanel";
import { CompareJobsRailPanel } from "../components/CompareJobsRailPanel";
import { ConfigPanel } from "../components/ConfigPanel";
import { PresetLibraryPanel } from "../components/PresetLibraryPanel";
import { useConfigStore } from "../stores/useConfigStore";
import { useRunStore } from "../stores/useRunStore";
import {
  cloneConfig,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
  HIGGS_DEMO_PRIMARY_OBSERVABLE,
} from "../lib/workbench";

export function CompareJobsPage() {
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

  function stagePreset(config: Parameters<typeof cloneConfig>[0], preferredObservable: string | null = null) {
    setDraftConfig(cloneConfig(config));
    setLoadedPresetName(config.name ?? null);
  }

  return (
    <>
      <Sidebar
        footer={
          <button type="button" className="primary-button w-full" disabled>
            Launch Compare Group
          </button>
        }
      >
        <CompareJobsRailPanel
          draftConfig={draftConfig}
          baselinePreset={baselinePreset}
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
          onStageHiggsDemo={() => stagePreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
          onLaunchHiggsDemo={() => stagePreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
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
            eyebrow="Comparison Planning"
            title="Stage A Managed Job Group"
            copy="Keep variant editing on the left rail and read the compare artifact framing in the main canvas."
          />
          <CompareJobsPlanningPanel
            draftConfig={draftConfig}
            baselinePreset={baselinePreset}
            baselinePresetName={baselinePresetName}
          />
        </section>
      </main>
    </>
  );
}
