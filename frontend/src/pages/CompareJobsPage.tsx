import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { SectionHeading } from "../components/ui/SectionHeading";
import { CompareJobsPlanningPanel } from "../components/CompareJobsPlanningPanel";
import { CompareJobsRailPanel } from "../components/CompareJobsRailPanel";
import { ConfigPanel } from "../components/ConfigPanel";
import { JobGroupResultPanel } from "../components/JobGroupResultPanel";
import { PresetLibraryPanel } from "../components/PresetLibraryPanel";
import { useConfigStore } from "../stores/useConfigStore";
import { useRunStore } from "../stores/useRunStore";
import { useJobGroups } from "../hooks/useJobGroups";
import {
  cloneConfig,
  selectHiggsDemoPreset,
  selectWorkingBaselinePreset,
  HIGGS_DEMO_PRIMARY_OBSERVABLE,
} from "../lib/workbench";
import type { JobGroupVariant } from "../api/types";

export function CompareJobsPage() {
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

  const [groupName, setGroupName] = useState("compare-group-1");
  const [variantLabel, setVariantLabel] = useState("variant-A");
  const [variantDesc, setVariantDesc] = useState("");

  const { groups, loading, error, selectedGroup, selectedGroupId, isLaunching, launchError, selectGroup, launchGroup, fetchGroups } =
    useJobGroups();

  const baselinePreset = selectWorkingBaselinePreset(presets);
  const higgsDemoPreset = selectHiggsDemoPreset(presets);
  const baselinePresetName = baselinePreset.name ?? null;
  const higgsDemoName = higgsDemoPreset.name ?? null;

  // Load runs for child status display
  useEffect(() => {
    runStore.fetchRuns();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize from URL params
  useEffect(() => {
    const groupId = searchParams.get("group");
    if (groupId && groups.length > 0 && !selectedGroupId) {
      selectGroup(groupId);
    }
  }, [groups.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync URL param for selected group
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (selectedGroupId) {
      params.set("group", selectedGroupId);
    } else {
      params.delete("group");
    }
    setSearchParams(params, { replace: true });
  }, [selectedGroupId]); // eslint-disable-line react-hooks/exhaustive-deps

  function stagePreset(config: Parameters<typeof cloneConfig>[0]) {
    setDraftConfig(cloneConfig(config));
    setLoadedPresetName(config.name ?? null);
  }

  async function handleLaunchGroup() {
    const variant: JobGroupVariant = {
      label: variantLabel,
      description: variantDesc || null,
      config_patch: {},
    };
    await launchGroup({
      study_id: "__none__",
      name: groupName,
      comparison_kind: "physics_hypothesis",
      base_config: draftConfig as Record<string, unknown>,
      variants: [variant],
    });
    fetchGroups();
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

          <CompareJobsRailPanel
            draftConfig={draftConfig}
            baselinePreset={baselinePreset.config}
            baselinePresetName={baselinePresetName}
          />
        </div>
      </div>

      {/* 下段: シミュレーション結果 */}
      <main className="flex-1 p-6 space-y-8">

        {/* Launch Form */}
        <section>
          <SectionHeading
            eyebrow="Job Group"
            title="Launch A Compare Group"
            copy="Define a base config and one or more variants. The backend will generate child runs automatically."
          />
          <div className="panel">
            <div className="panel-grid">
              <label className="field">
                <span className="field-label">Group Name</span>
                <input
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder="compare-group-1"
                  disabled={isLaunching}
                />
              </label>
              <label className="field">
                <span className="field-label">Variant Label</span>
                <input
                  value={variantLabel}
                  onChange={(e) => setVariantLabel(e.target.value)}
                  placeholder="variant-A"
                  disabled={isLaunching}
                />
              </label>
              <label className="field">
                <span className="field-label">Variant Description</span>
                <input
                  value={variantDesc}
                  onChange={(e) => setVariantDesc(e.target.value)}
                  placeholder="Optional description"
                  disabled={isLaunching}
                />
              </label>
            </div>
            <div style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className="primary-button"
                onClick={handleLaunchGroup}
                disabled={isLaunching || !groupName || !variantLabel}
              >
                {isLaunching ? "Launching…" : "Launch Group"}
              </button>
            </div>
            {launchError && <p className="state-banner state-error">{launchError}</p>}
          </div>
        </section>

        {/* Existing Groups */}
        <section>
          <SectionHeading
            eyebrow="History"
            title="Existing Job Groups"
            copy="Select a group to view its child run status and derived analysis results."
          />
          {error && <p className="state-banner state-error">{error}</p>}
          {loading && <p className="state-banner">Loading groups…</p>}
          {!loading && groups.length === 0 && (
            <div className="empty-card">
              <p>No job groups yet. Launch one above.</p>
            </div>
          )}
          <div className="run-list">
            {groups.map((group) => (
              <button
                key={group.group_id}
                type="button"
                className={`run-card ${group.group_id === selectedGroupId ? "run-card-selected" : ""}`}
                onClick={() => selectGroup(group.group_id)}
              >
                <div className="run-card-top">
                  <span className="run-card-name">{group.name}</span>
                  <span className={`status-pill status-${group.state}`}>{group.state}</span>
                </div>
                <div className="run-card-meta">
                  <span>{group.comparison_kind}</span>
                  <span>{(group.child_run_ids ?? []).length} runs</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Result */}
        <section>
          <SectionHeading
            eyebrow="Results"
            title="Job Group Output"
            copy="Child run statuses and k-spectral comparison when the group is complete."
          />
          <JobGroupResultPanel
            group={selectedGroup}
            allRuns={runs}
            studyId={null}
          />
        </section>

        {/* Planning (existing) */}
        <section>
          <SectionHeading
            eyebrow="Comparison Planning"
            title="Stage A Managed Job Group"
            copy="Keep variant editing on the left rail and read the compare artifact framing in the main canvas."
          />
          <CompareJobsPlanningPanel
            draftConfig={draftConfig}
            baselinePreset={baselinePreset.config}
            baselinePresetName={baselinePresetName}
          />
        </section>
      </main>
    </div>
  );
}
