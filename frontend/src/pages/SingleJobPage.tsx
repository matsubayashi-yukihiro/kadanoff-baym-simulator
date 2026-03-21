import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { StatusPill } from "../components/ui/StatusPill";
import { ConfigPanel } from "../components/ConfigPanel";
import { DiagnosticsPanel } from "../components/DiagnosticsPanel";
import { GreenFunctionPanel } from "../components/GreenFunctionPanel";
import { KSpectralPanel } from "../components/KSpectralPanel";
import { MixedGreenFunctionPanel } from "../components/MixedGreenFunctionPanel";
import { ObservablePanel } from "../components/ObservablePanel";
import { PresetLibraryPanel } from "../components/PresetLibraryPanel";
import { ResearchArtifactsPanel } from "../components/ResearchArtifactsPanel";
import { RunControlPanel } from "../components/RunControlPanel";
import { RunLogPanel } from "../components/RunLogPanel";
import { RunProgressPanel } from "../components/RunProgressPanel";
import { SpectrumPanel } from "../components/SpectrumPanel";
import { ThermalBranchPanel } from "../components/ThermalBranchPanel";
import { TrArpesPanel } from "../components/TrArpesPanel";
import { useConfigStore } from "../stores/useConfigStore";
import { useRunStore } from "../stores/useRunStore";
import { useObservableStore } from "../stores/useObservableStore";
import { useGreenFunctionStore } from "../stores/useGreenFunctionStore";
import { useResearchArtifacts } from "../hooks/useResearchArtifacts";
import { useRunProgress } from "../hooks/useRunProgress";
import {
  cloneConfig,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
  HIGGS_DEMO_PRIMARY_OBSERVABLE,
} from "../lib/workbench";
import { formatDateTime } from "../lib/format";
import type { PresetEntry, SimulationConfigInput } from "../api/types";

type ContourSurface = "real-time" | "thermal" | "mixed";

const CONTOUR_SURFACES: Array<{ key: ContourSurface; label: string; copy: string }> = [
  {
    key: "real-time",
    label: "Real-Time",
    copy: "Inspect retarded and lesser two-time slices first.",
  },
  {
    key: "thermal",
    label: "Thermal",
    copy: "Use Matsubara slices when thermal_branch is enabled.",
  },
  {
    key: "mixed",
    label: "Mixed",
    copy: "Read mixed real-time and imaginary-time slices for full contour dressing.",
  },
];

export function SingleJobPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeContourSurface, setActiveContourSurface] = useState<ContourSurface>("real-time");
  const [paramsOpen, setParamsOpen] = useState(false);

  // Config store
  const draftConfig = useConfigStore((s) => s.draftConfig);
  const setDraftConfig = useConfigStore((s) => s.setDraftConfig);
  const loadPreset = useConfigStore((s) => s.loadPreset);
  const resetDraft = useConfigStore((s) => s.resetDraft);
  const loadedPresetName = useConfigStore((s) => s.loadedPresetName);
  const setLoadedPresetName = useConfigStore((s) => s.setLoadedPresetName);
  const presets = useConfigStore((s) => s.presets);
  const presetsLoading = useConfigStore((s) => s.presetsLoading);
  const presetError = useConfigStore((s) => s.presetError);

  // Run store
  const runStore = useRunStore();
  const {
    runs,
    runsLoading,
    runsError,
    selectedRunId,
    selectedRun,
    runLoading,
    runError,
    isSubmitting,
    isCancelling,
    submitError,
    cancelError,
  } = runStore;

  // Observable store
  const obsStore = useObservableStore();

  // Green function store
  const gfStore = useGreenFunctionStore();

  // Research artifacts (studies, decision notes, evidence bundles)
  const artifacts = useResearchArtifacts(selectedRun, () => runStore.refresh());
  const progress = useRunProgress(
    selectedRunId,
    selectedRun?.state === "queued" || selectedRun?.state === "running",
  );

  const baselinePreset = selectWorkingBaselinePreset(presets);
  const higgsDemoPreset = selectHiggsDemoPreset(presets);
  const baselinePresetName = baselinePreset.name ?? null;
  const higgsDemoName = higgsDemoPreset.name ?? null;

  // Initialize from URL params
  useEffect(() => {
    const runId = searchParams.get("run");
    if (runId && !selectedRunId) {
      runStore.setSelectedRunId(runId);
    }
    const obs = searchParams.get("observable");
    if (obs) {
      obsStore.setSelectedObservable(obs);
    }
    const comp = searchParams.get("component");
    if (comp) {
      gfStore.setSelectedComponent(comp);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync URL params
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedRunId) params.set("run", selectedRunId);
    if (obsStore.selectedObservable) params.set("observable", obsStore.selectedObservable);
    if (gfStore.selectedComponent) params.set("component", gfStore.selectedComponent);
    if (loadedPresetName) params.set("preset", loadedPresetName);
    setSearchParams(params, { replace: true });
  }, [selectedRunId, obsStore.selectedObservable, gfStore.selectedComponent, loadedPresetName, setSearchParams]);

  // Fetch runs on mount + polling
  useEffect(() => {
    runStore.fetchRuns();
    const cleanup = runStore.startPolling();
    return cleanup;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch selected run detail
  useEffect(() => {
    runStore.fetchSelectedRun();
  }, [selectedRunId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch observables when run succeeds
  useEffect(() => {
    if (selectedRunId && selectedRun?.state === "succeeded") {
      obsStore.fetchCatalog(selectedRunId);
    } else {
      obsStore.resetForRun();
    }
  }, [selectedRunId, selectedRun?.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch observable data
  useEffect(() => {
    if (selectedRunId && obsStore.selectedObservable && selectedRun?.state === "succeeded") {
      obsStore.fetchData(selectedRunId, obsStore.selectedObservable);
    }
  }, [selectedRunId, obsStore.selectedObservable, selectedRun?.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch overlay data
  useEffect(() => {
    if (selectedRunId && selectedRun?.state === "succeeded") {
      for (const name of obsStore.overlayNames) {
        if (name !== obsStore.selectedObservable && !obsStore.overlayData.has(name)) {
          obsStore.fetchOverlay(selectedRunId, name);
        }
      }
    }
  }, [selectedRunId, selectedRun?.state, obsStore.overlayNames]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch green functions for kbe_hfb
  useEffect(() => {
    if (
      selectedRunId &&
      selectedRun?.state === "succeeded" &&
      selectedRun?.solver === "kbe_hfb"
    ) {
      gfStore.fetchCatalog(selectedRunId);
      if (selectedRun?.config?.thermal_branch?.enabled) {
        gfStore.fetchThermalCatalog(selectedRunId);
        gfStore.fetchMixedCatalog(selectedRunId);
      }
    } else {
      gfStore.resetAll();
    }
  }, [selectedRunId, selectedRun?.state, selectedRun?.solver]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch slices when params change
  useEffect(() => {
    if (selectedRunId && gfStore.catalog && gfStore.selectedComponent) {
      gfStore.fetchSlice(selectedRunId);
    }
  }, [selectedRunId, gfStore.selectedComponent, gfStore.rowIndex, gfStore.colIndex, gfStore.nambuStart, gfStore.nambuWindow]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedRunId && gfStore.thermalCatalog && gfStore.thermalComponent) {
      gfStore.fetchThermalSlice(selectedRunId);
    }
  }, [selectedRunId, gfStore.thermalComponent, gfStore.tauIndex, gfStore.thermalNambuStart, gfStore.thermalNambuWindow]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedRunId && gfStore.mixedCatalog && gfStore.mixedComponent) {
      gfStore.fetchMixedSlice(selectedRunId);
    }
  }, [selectedRunId, gfStore.mixedComponent, gfStore.mixedTimeIndex, gfStore.mixedTauIndex, gfStore.mixedNambuStart, gfStore.mixedNambuWindow]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-expand command deck when no run is selected
  useEffect(() => {
    if (!selectedRunId) setParamsOpen(true);
  }, [selectedRunId]);

  function stagePreset(config: PresetEntry | SimulationConfigInput, preferredObservable: string | null = null) {
    setDraftConfig(cloneConfig(config));
    setLoadedPresetName(config.name ?? null);
    if (preferredObservable) {
      obsStore.setSelectedObservable(preferredObservable);
    }
  }

  async function launchPreset(config: PresetEntry | SimulationConfigInput, preferredObservable: string | null = null) {
    stagePreset(config, preferredObservable);
    await runStore.createRun(cloneConfig(config));
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">

      {/* Command Deck */}
      <div className="sjp-command-deck">
        <div className="sjp-deck-header">
          <div className="sjp-deck-actions">
            {loadedPresetName && (
              <span className="sjp-preset-badge">{loadedPresetName}</span>
            )}
            <button
              type="button"
              className="primary-button"
              disabled={isSubmitting || isCancelling}
              onClick={() => runStore.createRun(draftConfig)}
            >
              {isSubmitting ? "Submitting…" : "Launch Run"}
            </button>
            {selectedRun && (selectedRun.state === "queued" || selectedRun.state === "running") ? (
              <button
                type="button"
                className="danger-button"
                disabled={isCancelling}
                onClick={() => runStore.cancelRun()}
              >
                {isCancelling ? "Cancelling…" : "Cancel Run"}
              </button>
            ) : null}
          </div>
          <button
            type="button"
            className="sjp-expand-btn"
            onClick={() => setParamsOpen((v) => !v)}
            aria-expanded={paramsOpen}
          >
            {paramsOpen ? "Hide Config ↑" : "Configure Run ↓"}
          </button>
        </div>
        {paramsOpen && (
          <div className="params-grid sjp-params-body">
            <ConfigPanel
              config={draftConfig}
              disabled={isSubmitting || isCancelling}
              onConfigChange={setDraftConfig}
              onReset={resetDraft}
            />
            <PresetLibraryPanel
              presets={presets}
              loading={presetsLoading}
              error={presetError}
              activePresetName={loadedPresetName}
              workingBaselineName={baselinePresetName}
              showHiggsQuickstart
              higgsDemoName={higgsDemoName}
              busy={isSubmitting || isCancelling}
              onLoadPreset={loadPreset}
              onStageHiggsDemo={() => stagePreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
              onLaunchHiggsDemo={() => launchPreset(higgsDemoPreset, HIGGS_DEMO_PRIMARY_OBSERVABLE)}
            />
            <RunControlPanel
              runs={runs}
              runsLoading={runsLoading}
              runsError={runsError}
              runLoading={runLoading}
              runError={runError}
              submitError={submitError}
              cancelError={cancelError}
              selectedRun={selectedRun}
              selectedRunId={selectedRunId}
              onRefresh={() => runStore.refresh()}
              onSelectRun={(id) => runStore.setSelectedRunId(id)}
            />
          </div>
        )}
      </div>

      {/* Run Identity Strip */}
      {selectedRun && (
        <div className="sjp-run-identity">
          <div className="sjp-run-identity-left">
            <StatusPill state={selectedRun.state} />
            <h2 className="sjp-run-name">{selectedRun.name}</h2>
            <code className="sjp-run-id">{selectedRun.run_id}</code>
          </div>
          <div className="sjp-run-identity-meta">
            <span className="sjp-run-meta-item">
              <span className="sjp-run-meta-label">Solver</span>
              <span className="sjp-run-meta-value">{selectedRun.solver}</span>
            </span>
            <span className="sjp-run-meta-item">
              <span className="sjp-run-meta-label">Created</span>
              <span className="sjp-run-meta-value">{formatDateTime(selectedRun.created_at)}</span>
            </span>
            {selectedRun.status_message && (
              <span className="sjp-run-status-msg">{selectedRun.status_message}</span>
            )}
          </div>
        </div>
      )}

      {/* Evidence Canvas */}
      <main className="flex-1 p-6 space-y-6">

        {/* Primary Evidence */}
        <div className="sjp-evidence-grid">
          <div className="space-y-4">
            <ObservablePanel
              catalog={obsStore.catalog}
              catalogLoading={obsStore.catalogLoading}
              catalogError={obsStore.catalogError}
              data={obsStore.data}
              dataLoading={obsStore.dataLoading}
              dataError={obsStore.dataError}
              run={selectedRun}
              selectedObservable={obsStore.selectedObservable}
              onSelectObservable={obsStore.setSelectedObservable}
              overlayNames={obsStore.overlayNames}
              onToggleOverlay={obsStore.toggleOverlay}
              overlayData={obsStore.overlayData}
            />
            <SpectrumPanel
              data={obsStore.data}
              dataLoading={obsStore.dataLoading}
              dataError={obsStore.dataError}
              run={selectedRun}
            />
          </div>
          <div className="sjp-support-rail">
            <RunProgressPanel
              run={selectedRun}
              progress={progress.progress}
              loading={progress.loading}
              error={progress.error}
              isStale={progress.isStale}
            />
            <DiagnosticsPanel run={selectedRun} />
            <RunLogPanel run={selectedRun} />
            <ResearchArtifactsPanel
              activeTab="single-job"
              run={selectedRun}
              selectedObservable={obsStore.selectedObservable}
              artifacts={artifacts}
            />
          </div>
        </div>

        {/* K-Space Derived Analysis — only for k_space runs */}
        {selectedRun?.config?.representation === "k_space" && (
          <div className="space-y-4">
            <KSpectralPanel
              run={selectedRun}
              studyId={selectedRun.research_metadata?.study_id}
            />
            <TrArpesPanel
              run={selectedRun}
              studyId={selectedRun.research_metadata?.study_id}
            />
          </div>
        )}

        {/* Advanced Evidence — Contour Surfaces */}
        <section>
          <div className="sjp-contour-tabbar" role="tablist" aria-label="Contour surface">
            {CONTOUR_SURFACES.map((surface) => (
              <button
                key={surface.key}
                role="tab"
                aria-selected={activeContourSurface === surface.key}
                className={`sjp-contour-tab${activeContourSurface === surface.key ? " active" : ""}`}
                onClick={() => setActiveContourSurface(surface.key)}
              >
                <span className="sjp-tab-label">{surface.label}</span>
                <span className="sjp-tab-copy">{surface.copy}</span>
              </button>
            ))}
            {selectedRun && (
              <div className="sjp-contour-tabbar-trailing">
                <StatusPill state={selectedRun.state} />
              </div>
            )}
          </div>
          <div className="space-y-4 pt-4">
            {activeContourSurface === "real-time" && (
              <GreenFunctionPanel
                run={selectedRun}
                catalog={gfStore.catalog}
                catalogLoading={gfStore.catalogLoading}
                catalogError={gfStore.catalogError}
                selectedComponent={gfStore.selectedComponent}
                onSelectComponent={gfStore.setSelectedComponent}
                rowIndex={gfStore.rowIndex}
                colIndex={gfStore.colIndex}
                nambuStart={gfStore.nambuStart}
                nambuWindow={gfStore.nambuWindow}
                onRowIndexChange={gfStore.setRowIndex}
                onColIndexChange={gfStore.setColIndex}
                onNambuStartChange={gfStore.setNambuStart}
                onNambuWindowChange={gfStore.setNambuWindow}
                slice={gfStore.slice}
                sliceLoading={gfStore.sliceLoading}
                sliceError={gfStore.sliceError}
              />
            )}
            {activeContourSurface === "thermal" && (
              <ThermalBranchPanel
                run={selectedRun}
                catalog={gfStore.thermalCatalog}
                catalogLoading={gfStore.thermalCatalogLoading}
                catalogError={gfStore.thermalCatalogError}
                selectedComponent={gfStore.thermalComponent}
                onSelectComponent={gfStore.setThermalComponent}
                tauIndex={gfStore.tauIndex}
                nambuStart={gfStore.thermalNambuStart}
                nambuWindow={gfStore.thermalNambuWindow}
                onTauIndexChange={gfStore.setTauIndex}
                onNambuStartChange={gfStore.setThermalNambuStart}
                onNambuWindowChange={gfStore.setThermalNambuWindow}
                slice={gfStore.thermalSlice}
                sliceLoading={gfStore.thermalSliceLoading}
                sliceError={gfStore.thermalSliceError}
              />
            )}
            {activeContourSurface === "mixed" && (
              <MixedGreenFunctionPanel
                run={selectedRun}
                catalog={gfStore.mixedCatalog}
                catalogLoading={gfStore.mixedCatalogLoading}
                catalogError={gfStore.mixedCatalogError}
                selectedComponent={gfStore.mixedComponent}
                onSelectComponent={gfStore.setMixedComponent}
                timeIndex={gfStore.mixedTimeIndex}
                tauIndex={gfStore.mixedTauIndex}
                nambuStart={gfStore.mixedNambuStart}
                nambuWindow={gfStore.mixedNambuWindow}
                onTimeIndexChange={gfStore.setMixedTimeIndex}
                onTauIndexChange={gfStore.setMixedTauIndex}
                onNambuStartChange={gfStore.setMixedNambuStart}
                onNambuWindowChange={gfStore.setMixedNambuWindow}
                slice={gfStore.mixedSlice}
                sliceLoading={gfStore.mixedSliceLoading}
                sliceError={gfStore.mixedSliceError}
              />
            )}
          </div>
        </section>

      </main>
    </div>
  );
}
