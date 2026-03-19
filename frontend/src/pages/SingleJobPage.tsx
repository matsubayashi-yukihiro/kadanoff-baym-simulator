import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Sidebar } from "../components/layout/Sidebar";
import { SectionHeading } from "../components/ui/SectionHeading";
import { Chip } from "../components/ui/Chip";
import { StatusPill } from "../components/ui/StatusPill";
import { Panel, PanelHeader } from "../components/ui/Panel";
import { ConfigPanel } from "../components/ConfigPanel";
import { DiagnosticsPanel } from "../components/DiagnosticsPanel";
import { GreenFunctionPanel } from "../components/GreenFunctionPanel";
import { MixedGreenFunctionPanel } from "../components/MixedGreenFunctionPanel";
import { ObservablePanel } from "../components/ObservablePanel";
import { PresetLibraryPanel } from "../components/PresetLibraryPanel";
import { ResearchArtifactsPanel } from "../components/ResearchArtifactsPanel";
import { RunContextPanel } from "../components/RunContextPanel";
import { RunControlPanel } from "../components/RunControlPanel";
import { RunLogPanel } from "../components/RunLogPanel";
import { SpectrumPanel } from "../components/SpectrumPanel";
import { ThermalBranchPanel } from "../components/ThermalBranchPanel";
import { ValidationScopePanel } from "../components/ValidationScopePanel";
import { useConfigStore } from "../stores/useConfigStore";
import { useRunStore } from "../stores/useRunStore";
import { useObservableStore } from "../stores/useObservableStore";
import { useGreenFunctionStore } from "../stores/useGreenFunctionStore";
import {
  cloneConfig,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
  HIGGS_DEMO_PRIMARY_OBSERVABLE,
} from "../lib/workbench";
import type { PresetConfig, SimulationConfigInput } from "../api/types";

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

  const baselinePreset = selectWorkingBaselinePreset(presets);
  const higgsDemoPreset = selectHiggsDemoPreset(presets);
  const baselinePresetName = baselinePreset.name ?? null;
  const higgsDemoName = higgsDemoPreset.name ?? null;

  const evidenceSurface =
    selectedRun?.solver === "kbe_hfb"
      ? "Observables, diagnostics, and two-time contour slices are available."
      : "Observables and diagnostics are the primary evidence surfaces.";

  const activeContour =
    CONTOUR_SURFACES.find((s) => s.key === activeContourSurface) ?? CONTOUR_SURFACES[0];

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

  function stagePreset(config: PresetConfig | SimulationConfigInput, preferredObservable: string | null = null) {
    setDraftConfig(cloneConfig(config));
    setLoadedPresetName(config.name ?? null);
    if (preferredObservable) {
      obsStore.setSelectedObservable(preferredObservable);
    }
  }

  async function launchPreset(config: PresetConfig | SimulationConfigInput, preferredObservable: string | null = null) {
    stagePreset(config, preferredObservable);
    await runStore.createRun(cloneConfig(config));
  }

  return (
    <>
      <Sidebar
        footer={
          <div className="space-y-2">
            <button
              type="button"
              className="primary-button w-full"
              disabled={isSubmitting || isCancelling}
              onClick={() => runStore.createRun(draftConfig)}
            >
              {isSubmitting ? "Submitting..." : "Launch Run"}
            </button>
            {selectedRun && (selectedRun.state === "queued" || selectedRun.state === "running") ? (
              <button
                type="button"
                className="danger-button w-full"
                disabled={isCancelling}
                onClick={() => runStore.cancelRun()}
              >
                {isCancelling ? "Cancelling..." : "Cancel Run"}
              </button>
            ) : null}
          </div>
        }
      >
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

        <ConfigPanel
          config={draftConfig}
          disabled={isSubmitting || isCancelling}
          onConfigChange={setDraftConfig}
          onReset={resetDraft}
        />

        <RunControlPanel
          isSubmitting={isSubmitting}
          isCancelling={isCancelling}
          runs={runs}
          runsLoading={runsLoading}
          runsError={runsError}
          runLoading={runLoading}
          runError={runError}
          submitError={submitError}
          cancelError={cancelError}
          selectedRun={selectedRun}
          selectedRunId={selectedRunId}
          onCreateRun={() => runStore.createRun(draftConfig)}
          onCancelRun={() => runStore.cancelRun()}
          onRefresh={() => runStore.refresh()}
          onSelectRun={(id) => runStore.setSelectedRunId(id)}
        />
      </Sidebar>

      <main className="flex-1 overflow-y-auto p-6 space-y-8">
        {/* Run Framing */}
        <section>
          <SectionHeading
            eyebrow="Run Framing"
            title="Set Claim Boundary Before Reading Evidence"
            copy="Keep preset loading, config editing, and run selection on the left rail."
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ValidationScopePanel draftConfig={draftConfig} selectedRun={selectedRun} />
            <RunContextPanel
              run={selectedRun}
              baselinePreset={baselinePreset}
              evidenceSurface={evidenceSurface}
            />
          </div>
        </section>

        {/* Primary Evidence */}
        <section>
          <SectionHeading
            eyebrow="Primary Evidence"
            title="Read Observables Before Diagnostics And Contours"
            copy="Keep the first pass on stored observables and spectrum preview."
          />
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_340px] gap-4">
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
            <div className="space-y-4">
              <DiagnosticsPanel run={selectedRun} />
              <RunLogPanel run={selectedRun} />
              <ResearchArtifactsPanel
                activeTab="single-job"
                run={selectedRun}
                selectedObservable={obsStore.selectedObservable}
              />
            </div>
          </div>
        </section>

        {/* Advanced Evidence - Contours */}
        <section>
          <SectionHeading
            eyebrow="Advanced Evidence"
            title="Inspect Contour-Dressed Artifacts On Demand"
            copy="Real-time slices first; open thermal or mixed contour as needed."
          />
          <div className="grid grid-cols-1 xl:grid-cols-[280px_1fr] gap-4">
            <Panel>
              <PanelHeader eyebrow="Contour Surface" title="Choose What To Inspect">
                {selectedRun ? <StatusPill state={selectedRun.state} /> : null}
              </PanelHeader>
              <div className="flex gap-2 mb-3" role="tablist" aria-label="Contour surface selector">
                {CONTOUR_SURFACES.map((surface) => (
                  <Chip
                    key={surface.key}
                    label={surface.label}
                    active={activeContourSurface === surface.key}
                    onClick={() => setActiveContourSurface(surface.key)}
                  />
                ))}
              </div>
              <p className="text-xs text-ink-muted">{activeContour.copy}</p>
            </Panel>

            <div className="space-y-4">
              {activeContourSurface === "real-time" ? (
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
              ) : null}

              {activeContourSurface === "thermal" ? (
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
              ) : null}

              {activeContourSurface === "mixed" ? (
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
              ) : null}
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
