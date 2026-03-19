import { useConfigStore } from "../../stores/useConfigStore";
import { useRunStore } from "../../stores/useRunStore";
import { getSimulationTrack } from "../../lib/projectNarrative";

export function TopBar() {
  const draftConfig = useConfigStore((s) => s.draftConfig);
  const loadedPresetName = useConfigStore((s) => s.loadedPresetName);
  const selectedRun = useRunStore((s) => s.selectedRun);

  const draftTrack = getSimulationTrack(draftConfig);
  const selectedTrack = selectedRun ? getSimulationTrack(selectedRun.config) : null;

  return (
    <header className="w-full px-6 py-4 flex items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">TDKB</p>
          <span className="w-px h-4 bg-border-soft" aria-hidden="true" />
          <span className="text-xs text-ink-muted">Research Workbench</span>
        </div>
        <h1 className="font-heading text-2xl font-semibold text-ink leading-tight">
          Research Workbench
        </h1>
      </div>

      <div className="flex items-center gap-2 flex-wrap justify-end">
        <ValidationPill tone={draftTrack.tone} label={`Draft: ${draftTrack.statusLabel}`} />
        {selectedTrack ? (
          <ValidationPill tone={selectedTrack.tone} label={`Selected: ${selectedTrack.statusLabel}`} />
        ) : null}
        {loadedPresetName ? (
          <span className="px-3 py-1 rounded-full text-xs font-medium bg-accent-soft/30 text-ink-subtle">
            Preset: {loadedPresetName}
          </span>
        ) : null}
      </div>
    </header>
  );
}

function ValidationPill({ tone, label }: { tone: string; label: string }) {
  const colorMap: Record<string, string> = {
    validated: "bg-success/10 text-success",
    partial: "bg-queued/10 text-queued",
    prototype: "bg-accent/10 text-accent",
    future: "bg-ink-muted/10 text-ink-muted",
  };

  return (
    <span className={`px-3 py-1 rounded-full text-xs font-medium ${colorMap[tone] ?? colorMap.future}`}>
      {label}
    </span>
  );
}
