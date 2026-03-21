import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { SectionHeading } from "../components/ui/SectionHeading";
import { ConfigPanel } from "../components/ConfigPanel";
import { PresetLibraryPanel } from "../components/PresetLibraryPanel";
import { SweepRailPanel } from "../components/SweepRailPanel";
import { SweepResultPanel } from "../components/SweepResultPanel";
import { useConfigStore } from "../stores/useConfigStore";
import { useRunStore } from "../stores/useRunStore";
import { useSweeps } from "../hooks/useSweeps";
import {
  cloneConfig,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
} from "../lib/workbench";

export function ParameterSweepPage() {
  const [searchParams, setSearchParams] = useSearchParams();
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
  const runs = useRunStore((s) => s.runs);
  const runStore = useRunStore();

  const [sweepName, setSweepName] = useState("sweep-1");

  const {
    sweeps,
    loading,
    error,
    selectedSweep,
    selectedSweepId,
    isLaunching,
    launchError,
    selectSweep,
    launchSweep,
  } = useSweeps();

  const baselinePreset = selectWorkingBaselinePreset(presets);
  const higgsDemoPreset = selectHiggsDemoPreset(presets);
  const baselinePresetName = baselinePreset.name ?? null;
  const higgsDemoName = higgsDemoPreset.name ?? null;

  useEffect(() => {
    runStore.fetchRuns();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize from URL params
  useEffect(() => {
    const sweepId = searchParams.get("sweep");
    if (sweepId && sweeps.length > 0 && !selectedSweepId) {
      selectSweep(sweepId);
    }
  }, [sweeps.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync URL param for selected sweep
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (selectedSweepId) {
      params.set("sweep", selectedSweepId);
    } else {
      params.delete("sweep");
    }
    setSearchParams(params, { replace: true });
  }, [selectedSweepId]); // eslint-disable-line react-hooks/exhaustive-deps

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
            onLaunch={launchSweep}
            isLaunching={isLaunching}
            sweepName={sweepName}
            onSweepNameChange={setSweepName}
          />
        </div>
      </div>

      {/* 下段: シミュレーション結果 */}
      <main className="flex-1 p-6 space-y-8">

        {launchError && <p className="state-banner state-error">{launchError}</p>}

        {/* Existing sweeps */}
        <section>
          <SectionHeading
            eyebrow="History"
            title="Existing Sweeps"
            copy="Select a sweep to view child run progress and tr-ARPES heatmap."
          />
          {error && <p className="state-banner state-error">{error}</p>}
          {loading && <p className="state-banner">Loading sweeps…</p>}
          {!loading && sweeps.length === 0 && (
            <div className="empty-card">
              <p>No sweeps yet. Configure and launch one above.</p>
            </div>
          )}
          <div className="run-list">
            {sweeps.map((sweep) => (
              <button
                key={sweep.sweep_id}
                type="button"
                className={`run-card ${sweep.sweep_id === selectedSweepId ? "run-card-selected" : ""}`}
                onClick={() => selectSweep(sweep.sweep_id)}
              >
                <div className="run-card-top">
                  <span className="run-card-name">{sweep.name}</span>
                  <span className={`status-pill status-${sweep.state}`}>{sweep.state}</span>
                </div>
                <div className="run-card-meta">
                  <span>{sweep.parameter_label}</span>
                  <span>{(sweep.child_run_ids ?? []).length} runs</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Result */}
        <section>
          <SectionHeading
            eyebrow="Results"
            title="Sweep Output"
            copy="Child run progress and tr-ARPES intensity heatmap when complete."
          />
          <SweepResultPanel
            sweep={selectedSweep}
            allRuns={runs}
            studyId={null}
          />
        </section>

      </main>
    </div>
  );
}
