import { useState } from "react";

import type { PresetEntry, SimulationConfigInput } from "./api/types";
import { CompareJobsPlanningPanel } from "./components/CompareJobsPlanningPanel";
import { CompareJobsRailPanel } from "./components/CompareJobsRailPanel";
import { ConfigPanel } from "./components/ConfigPanel";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { GreenFunctionPanel } from "./components/GreenFunctionPanel";
import { MixedGreenFunctionPanel } from "./components/MixedGreenFunctionPanel";
import { ObservablePanel } from "./components/ObservablePanel";
import { PresetLibraryPanel } from "./components/PresetLibraryPanel";
import { ResearchArtifactsPanel } from "./components/ResearchArtifactsPanel";
import { RunLogPanel } from "./components/RunLogPanel";
import { RunProgressPanel } from "./components/RunProgressPanel";
import { RunControlPanel } from "./components/RunControlPanel";
import { SpectrumPanel } from "./components/SpectrumPanel";
import { ThermalBranchPanel } from "./components/ThermalBranchPanel";
import { WorkbenchPlaceholderPanel } from "./components/WorkbenchPlaceholderPanel";
import { WorkbenchTabs } from "./components/WorkbenchTabs";
import { useGreenFunctions } from "./hooks/useGreenFunctions";
import { useMixedGreenFunctions } from "./hooks/useMixedGreenFunctions";
import { useObservables } from "./hooks/useObservables";
import { usePresets } from "./hooks/usePresets";
import { useResearchArtifacts } from "./hooks/useResearchArtifacts";
import { useRunProgress } from "./hooks/useRunProgress";
import { useRuns } from "./hooks/useRuns";
import { useThermalBranch } from "./hooks/useThermalBranch";
import { readUrlState, useUrlStateSync } from "./hooks/useUrlState";
import { createDefaultConfig } from "./lib/defaultConfig";
import { isTerminalState } from "./lib/helpers";
import { getSimulationTrack } from "./lib/projectNarrative";
import {
  cloneConfig,
  getWorkbenchTabDescriptor,
  HIGGS_DEMO_PRIMARY_OBSERVABLE,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
  type WorkbenchTab,
} from "./lib/workbench";

const DEFAULT_TAB: WorkbenchTab = "single-job";
type ContourSurface = "real-time" | "thermal" | "mixed";

const CONTOUR_SURFACES: Array<{ key: ContourSurface; label: string; copy: string }> = [
  {
    key: "real-time",
    label: "Real-Time",
    copy: "Inspect retarded and lesser two-time slices first. This is the primary contour surface for reading stored Keldysh structure.",
  },
  {
    key: "thermal",
    label: "Thermal",
    copy: "Use Matsubara slices when thermal_branch is enabled and the selected run needs finite-temperature contour context.",
  },
  {
    key: "mixed",
    label: "Mixed",
    copy: "Read mixed real-time and imaginary-time slices only when you need full contour dressing evidence beyond the real-time view.",
  },
];

export default function App() {
  const initialUrlState = readUrlState();

  const [activeTab, setActiveTab] = useState<WorkbenchTab>(() => initialUrlState.tab ?? DEFAULT_TAB);
  const [activeContourSurface, setActiveContourSurface] = useState<ContourSurface>("real-time");
  const [draftConfig, setDraftConfig] = useState<SimulationConfigInput>(() => createDefaultConfig());
  const [loadedPresetName, setLoadedPresetName] = useState<string | null>(() => initialUrlState.presetName ?? null);

  const { presets, presetsLoading, presetError } = usePresets();

  const runState = useRuns(initialUrlState.runId ?? null);
  const { selectedRunId, selectedRun, isSubmitting, isCancelling } = runState;

  const observables = useObservables(selectedRunId, selectedRun, initialUrlState.observable ?? null);
  const runProgress = useRunProgress(selectedRunId, selectedRun?.state === "queued" || selectedRun?.state === "running");
  const green = useGreenFunctions(selectedRunId, selectedRun, initialUrlState.component ?? null);
  const thermal = useThermalBranch(selectedRunId, selectedRun);
  const mixed = useMixedGreenFunctions(selectedRunId, selectedRun);
  const artifacts = useResearchArtifacts(selectedRun, () => runState.refresh());

  const canCancel = Boolean(selectedRun && !isTerminalState(selectedRun.state));
  const isSingleJobPage = activeTab === "single-job";
  const isCompareJobsPage = activeTab === "compare-jobs";
  const isParameterSweepPage = activeTab === "parameter-sweep";

  useUrlStateSync({
    tab: activeTab,
    runId: isSingleJobPage ? selectedRunId : null,
    observable: isSingleJobPage ? observables.selectedObservable : null,
    component: isSingleJobPage ? green.selectedComponent : null,
    presetName: loadedPresetName,
  });

  function handleLoadPreset(preset: PresetEntry) {
    setDraftConfig(cloneConfig(preset));
    setLoadedPresetName(preset.name ?? null);
  }

  function resetDraft() {
    setDraftConfig(createDefaultConfig());
    setLoadedPresetName(null);
  }

  function stagePreset(config: PresetEntry | SimulationConfigInput, preferredObservable: string | null = null) {
    const nextConfig = cloneConfig(config);
    setActiveTab("single-job");
    setActiveContourSurface("real-time");
    setDraftConfig(nextConfig);
    setLoadedPresetName(nextConfig.name ?? null);
    if (preferredObservable) {
      observables.setSelectedObservable(preferredObservable);
    }
  }

  async function launchPreset(config: PresetEntry | SimulationConfigInput, preferredObservable: string | null = null) {
    const nextConfig = cloneConfig(config);
    stagePreset(nextConfig, preferredObservable);
    await runState.createRun(nextConfig);
  }

  const activeSurface = getWorkbenchTabDescriptor(activeTab);
  const draftTrack = getSimulationTrack(draftConfig);
  const selectedTrack = selectedRun ? getSimulationTrack(selectedRun.config) : null;
  const activePresetName = loadedPresetName;
  const baselinePreset = selectWorkingBaselinePreset(presets);
  const higgsDemoPreset = selectHiggsDemoPreset(presets);
  const baselinePresetName = baselinePreset.name ?? null;
  const higgsDemoName = higgsDemoPreset.name ?? null;
  const activeContour = CONTOUR_SURFACES.find((surface) => surface.key === activeContourSurface) ?? CONTOUR_SURFACES[0];

  return (
    <div className="app-shell">
      <div className="app-backdrop" />

      <header className="shell-topbar">
        <div className="shell-brand">
          <div className="shell-topline">
            <p className="hero-kicker">TDKB</p>
            <span className="shell-divider" aria-hidden="true" />
            <span className="shell-surface-label">{activeSurface.label}</span>
          </div>
          <h1>Research Workbench</h1>
          <p className="shell-copy">{activeSurface.summary}</p>
        </div>

        <div className="shell-badge-cluster">
          <span className={`validation-pill validation-${draftTrack.tone}`}>Draft: {draftTrack.statusLabel}</span>
          {isSingleJobPage && selectedTrack ? (
            <span className={`validation-pill validation-${selectedTrack.tone}`}>
              Selected run: {selectedTrack.statusLabel}
            </span>
          ) : null}
          <span className="signal-badge">{isSingleJobPage ? "Single-run evidence" : "Planning surface"}</span>
          {activePresetName ? <span className="signal-badge">Preset: {activePresetName}</span> : null}
        </div>
      </header>

      <WorkbenchTabs activeTab={activeTab} onSelectTab={setActiveTab} />

      <div className="shell-layout">
        <div className="params-strip">
          {isSingleJobPage ? (
            <div className="params-grid">
              <div className="params-config-col">
                <div className="params-action-bar">
                  <button type="button" className="primary-button" onClick={() => runState.createRun(draftConfig)} disabled={isSubmitting}>
                    {isSubmitting ? "Submitting..." : "Launch Run"}
                  </button>
                  {canCancel ? (
                    <button type="button" className="danger-button" onClick={runState.cancelRun} disabled={isCancelling}>
                      {isCancelling ? "Cancelling..." : "Cancel"}
                    </button>
                  ) : null}
                  {runState.submitError ? <p className="state-banner state-error" style={{fontSize: "0.82rem", padding: "0.4rem 0.6rem"}}>{runState.submitError}</p> : null}
                </div>
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
                activePresetName={activePresetName}
                workingBaselineName={baselinePresetName}
                showHiggsQuickstart
                higgsDemoName={higgsDemoName}
                busy={isSubmitting || isCancelling}
                onLoadPreset={handleLoadPreset}
                onStageHiggsDemo={() => stagePreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
                onLaunchHiggsDemo={() => launchPreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
              />

              <RunControlPanel
                runs={runState.runs}
                runsLoading={runState.runsLoading}
                runsError={runState.runsError}
                runLoading={runState.runLoading}
                runError={runState.runError}
                submitError={runState.submitError}
                cancelError={runState.cancelError}
                selectedRun={runState.selectedRun}
                selectedRunId={runState.selectedRunId}
                onRefresh={runState.refresh}
                onSelectRun={runState.setSelectedRunId}
              />
            </div>
          ) : null}

          {isCompareJobsPage ? (
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
                activePresetName={activePresetName}
                workingBaselineName={baselinePresetName}
                showHiggsQuickstart={false}
                higgsDemoName={higgsDemoName}
                busy={isSubmitting || isCancelling}
                onLoadPreset={handleLoadPreset}
                onStageHiggsDemo={() => stagePreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
                onLaunchHiggsDemo={() => launchPreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
              />

              <CompareJobsRailPanel
                draftConfig={draftConfig}
                baselinePreset={baselinePreset.config}
                baselinePresetName={baselinePresetName}
              />
            </div>
          ) : null}

          {isParameterSweepPage ? (
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
                activePresetName={activePresetName}
                workingBaselineName={baselinePresetName}
                showHiggsQuickstart={false}
                higgsDemoName={higgsDemoName}
                busy={isSubmitting || isCancelling}
                onLoadPreset={handleLoadPreset}
                onStageHiggsDemo={() => stagePreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
                onLaunchHiggsDemo={() => launchPreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
              />
            </div>
          ) : null}
        </div>

        <main className="shell-main page-stack">
          {isSingleJobPage ? (
            <>
              <section className="page-section">
                <div className="section-heading-row">
                  <div>
                    <p className="eyebrow">Primary Evidence</p>
                    <h2>Read Observables Before Diagnostics And Contours</h2>
                  </div>
                  <p className="section-copy">
                    Keep the first pass on stored observables and spectrum preview. Diagnostics, logs, and artifact
                    backlog stay on the support rail instead of competing with the primary read.
                  </p>
                </div>

                <div className="single-job-evidence-grid">
                  <div className="flow-column">
                    <ObservablePanel
                      catalog={observables.catalog}
                      catalogLoading={observables.catalogLoading}
                      catalogError={observables.catalogError}
                      data={observables.data}
                      dataLoading={observables.dataLoading}
                      dataError={observables.dataError}
                      run={selectedRun}
                      selectedObservable={observables.selectedObservable}
                      onSelectObservable={observables.setSelectedObservable}
                      overlayNames={observables.overlayNames}
                      onToggleOverlay={observables.toggleOverlay}
                      overlayData={observables.overlayData}
                    />

                    <SpectrumPanel
                      data={observables.data}
                      dataLoading={observables.dataLoading}
                      dataError={observables.dataError}
                      run={selectedRun}
                    />
                  </div>

                  <div className="flow-column evidence-support-rail control-rail-sticky">
                    <RunProgressPanel
                      run={selectedRun}
                      progress={runProgress.progress}
                      loading={runProgress.loading}
                      error={runProgress.error}
                      isStale={runProgress.isStale}
                      staleDetails={runProgress.staleDetails}
                    />
                    <DiagnosticsPanel run={selectedRun} />
                    <RunLogPanel run={selectedRun} />
                    <ResearchArtifactsPanel
                      activeTab={activeTab}
                      run={selectedRun}
                      selectedObservable={observables.selectedObservable}
                      artifacts={artifacts}
                    />
                  </div>
                </div>
              </section>

              <section className="page-section">
                <div className="section-heading-row">
                  <div>
                    <p className="eyebrow">Advanced Evidence</p>
                    <h2>Inspect Contour-Dressed Artifacts On Demand</h2>
                  </div>
                  <p className="section-copy">
                    Keep real-time slices first and open thermal or mixed contour structure only when the selected run
                    requires full-contour context.
                  </p>
                </div>

                <div className="single-job-advanced-grid">
                  <section className="panel contour-stage-panel">
                    <div className="panel-header">
                      <div>
                        <p className="eyebrow">Contour Surface</p>
                        <h2>Choose What To Inspect</h2>
                      </div>
                      {selectedRun ? <span className={`status-pill status-${selectedRun.state}`}>{selectedRun.state}</span> : null}
                    </div>

                    <div className="chip-row" role="tablist" aria-label="Contour surface selector">
                      {CONTOUR_SURFACES.map((surface) => (
                        <button
                          key={surface.key}
                          type="button"
                          className={`chip ${activeContourSurface === surface.key ? "chip-active" : ""}`}
                          onClick={() => setActiveContourSurface(surface.key)}
                        >
                          {surface.label}
                        </button>
                      ))}
                    </div>

                    <p className="field-hint contour-stage-copy">{activeContour.copy}</p>
                  </section>

                  <div className="flow-column">
                    {activeContourSurface === "real-time" ? (
                      <GreenFunctionPanel
                        run={selectedRun}
                        catalog={green.catalog}
                        catalogLoading={green.catalogLoading}
                        catalogError={green.catalogError}
                        selectedComponent={green.selectedComponent}
                        onSelectComponent={green.setSelectedComponent}
                        rowIndex={green.rowIndex}
                        colIndex={green.colIndex}
                        nambuStart={green.nambuStart}
                        nambuWindow={green.nambuWindow}
                        onRowIndexChange={green.setRowIndex}
                        onColIndexChange={green.setColIndex}
                        onNambuStartChange={green.setNambuStart}
                        onNambuWindowChange={green.setNambuWindow}
                        slice={green.slice}
                        sliceLoading={green.sliceLoading}
                        sliceError={green.sliceError}
                      />
                    ) : null}

                    {activeContourSurface === "thermal" ? (
                      <ThermalBranchPanel
                        run={selectedRun}
                        catalog={thermal.catalog}
                        catalogLoading={thermal.catalogLoading}
                        catalogError={thermal.catalogError}
                        selectedComponent={thermal.selectedComponent}
                        onSelectComponent={thermal.setSelectedComponent}
                        tauIndex={thermal.tauIndex}
                        nambuStart={thermal.nambuStart}
                        nambuWindow={thermal.nambuWindow}
                        onTauIndexChange={thermal.setTauIndex}
                        onNambuStartChange={thermal.setNambuStart}
                        onNambuWindowChange={thermal.setNambuWindow}
                        slice={thermal.slice}
                        sliceLoading={thermal.sliceLoading}
                        sliceError={thermal.sliceError}
                      />
                    ) : null}

                    {activeContourSurface === "mixed" ? (
                      <MixedGreenFunctionPanel
                        run={selectedRun}
                        catalog={mixed.catalog}
                        catalogLoading={mixed.catalogLoading}
                        catalogError={mixed.catalogError}
                        selectedComponent={mixed.selectedComponent}
                        onSelectComponent={mixed.setSelectedComponent}
                        timeIndex={mixed.timeIndex}
                        tauIndex={mixed.tauIndex}
                        nambuStart={mixed.nambuStart}
                        nambuWindow={mixed.nambuWindow}
                        onTimeIndexChange={mixed.setTimeIndex}
                        onTauIndexChange={mixed.setTauIndex}
                        onNambuStartChange={mixed.setNambuStart}
                        onNambuWindowChange={mixed.setNambuWindow}
                        slice={mixed.slice}
                        sliceLoading={mixed.sliceLoading}
                        sliceError={mixed.sliceError}
                      />
                    ) : null}
                  </div>
                </div>
              </section>
            </>
          ) : isCompareJobsPage ? (
            <section className="page-section">
              <div className="section-heading-row">
                <div>
                  <p className="eyebrow">Comparison Planning</p>
                  <h2>Stage A Managed Job Group</h2>
                </div>
                <p className="section-copy">
                  Keep variant editing on the left rail and read the compare artifact framing in the main canvas before
                  any future overlay, difference, or FFT panels arrive.
                </p>
              </div>

              <CompareJobsPlanningPanel
                draftConfig={draftConfig}
                baselinePreset={baselinePreset.config}
                baselinePresetName={baselinePresetName}
              />
            </section>
          ) : (
            <section className="page-section">
              <div className="section-heading-row">
                <div>
                  <p className="eyebrow">Sweep Planning</p>
                  <h2>Design A Managed Sweep</h2>
                </div>
                <p className="section-copy">
                  Use this page for scan setup and guardrails. Do not mix parameter-scan planning into the single-run
                  evidence reading path.
                </p>
              </div>

              <WorkbenchPlaceholderPanel
                tab={activeTab}
                draftConfig={draftConfig}
                baselinePresetName={baselinePresetName}
              />
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
