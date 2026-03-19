import type { WorkbenchTab } from "../lib/workbench";
import type { SimulationConfigInput } from "../api/types";
import { getSimulationTrack } from "../lib/projectNarrative";
import { COMPARE_TEMPLATES, SWEEP_TEMPLATES, WORKING_STUDY } from "../lib/workbench";

type WorkbenchPlaceholderPanelProps = {
  tab: WorkbenchTab;
  draftConfig: SimulationConfigInput;
  baselinePresetName: string | null;
};

export function WorkbenchPlaceholderPanel(props: WorkbenchPlaceholderPanelProps) {
  const { tab, draftConfig, baselinePresetName } = props;
  const isCompare = tab === "compare-jobs";
  const templates = isCompare ? COMPARE_TEMPLATES : SWEEP_TEMPLATES;
  const draftTrack = getSimulationTrack(draftConfig);
  const guardrails = isCompare
    ? [
        "Keep physics hypothesis compare and numerical validation compare explicit via `comparison_kind`.",
        "`second_born` and `second_born_reference` must stay separate in labels, notes, and summaries.",
        "Accepted or rejected judgments belong to the future `job group` artifact, not to ad hoc dashboard annotations.",
      ]
    : [
        "Keep `parameter_kind` explicit so physics sweeps and numerical sweeps do not blur together.",
        "Time and frequency heatmaps should be tied to fixed-grid alignment; otherwise use convergence rows or error surfaces.",
        "`dt`, adaptive tolerance, and memory-window scans should read as numerical validation work, not as physics evidence by default.",
      ];

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{isCompare ? "Compare Jobs" : "Parameter Sweep"}</p>
          <h2>{isCompare ? "Comparison Design Surface" : "Sweep Design Surface"}</h2>
        </div>
      </div>

      <p className="state-banner">
        {isCompare
          ? "Keep comparison setup off the Single Job page. This surface will attach to backend-managed `job group` artifacts once the registry and compare APIs land."
          : "Keep sweep setup off the Single Job page. This surface will attach to backend-managed `sweep` artifacts once the registry and sweep APIs land."}
      </p>

      <div className="note-grid note-grid-2">
        <article className="note-card">
          <span className="briefing-label">Working Question</span>
          <p>{WORKING_STUDY.question}</p>
        </article>
        <article className="note-card">
          <span className="briefing-label">Current Draft</span>
          <p>
            {draftConfig.name ?? "Untitled draft"} is currently targeting {draftTrack.title} with baseline{" "}
            {baselinePresetName ?? "pending"}.
          </p>
        </article>
        <article className="note-card">
          <span className="briefing-label">Required Backend Step</span>
          <p>
            {isCompare
              ? "Implement experiment registry plus `job-groups` APIs with comparison_kind, baseline_run_id, and child-run lineage."
              : "Implement experiment registry plus `sweeps` APIs with parameter_path, parameter_kind, fixed_axes, and child-run lineage."}
          </p>
        </article>
        <article className="note-card">
          <span className="briefing-label">This Page Exists To</span>
          <p>
            {isCompare
              ? "Prepare comparison artifacts, variant labels, and baseline intent before overlay, difference, FFT compare, and failure-aware summaries land."
              : "Prepare sweep metadata before parameter x time, parameter x frequency, convergence-row, and error-surface views land."}
          </p>
        </article>
      </div>

      <div className="panel-subheader">
        <h3>First Templates</h3>
      </div>

      <div className="stack-list">
        {templates.map((item) => (
          <article key={item} className="stack-item">
            <p>{item}</p>
          </article>
        ))}
      </div>

      <div className="panel-subheader">
        <h3>Guardrails</h3>
      </div>

      <div className="stack-list">
        {guardrails.map((item) => (
          <article key={item} className="stack-item">
            <p>{item}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
