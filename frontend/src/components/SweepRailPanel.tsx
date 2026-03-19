import { useState, useMemo } from "react";
import type { SimulationConfigInput } from "../api/types";
import { SWEEP_TEMPLATES } from "../lib/workbench";

type SweepRailPanelProps = {
  draftConfig: SimulationConfigInput;
  baselinePresetName: string | null;
};

const SWEEPABLE_PATHS = [
  "lattice.chemical_potential",
  "drive.amplitude_x",
  "drive.frequency",
  "drive.width",
  "interaction.onsite_u",
  "interaction.nearest_neighbor_v",
  "initial_state.temperature",
  "initial_state.filling",
  "initial_state.seed_pairing",
  "time.dt",
  "kbe.mixing",
  "kbe.tolerance",
  "adaptive.min_dt",
  "adaptive.max_dt",
  "thermal_branch.n_tau",
] as const;

type SweepablePath = (typeof SWEEPABLE_PATHS)[number];

const NUMERICAL_PREFIXES = ["time.", "kbe.", "adaptive.", "thermal_branch."];

function inferParameterKind(path: string): "numerical" | "physics" {
  return NUMERICAL_PREFIXES.some((prefix) => path.startsWith(prefix))
    ? "numerical"
    : "physics";
}

function resolveBaselineValue(
  config: SimulationConfigInput,
  path: SweepablePath,
): string {
  const [section, key] = path.split(".") as [string, string];
  const group = config[section as keyof SimulationConfigInput];
  if (group != null && typeof group === "object" && key in group) {
    const val = (group as Record<string, unknown>)[key];
    if (val == null) return "-";
    return String(val);
  }
  return "-";
}

function describeFixedAxes(
  config: SimulationConfigInput,
  selectedPath: string,
): string[] {
  const fixed: string[] = [];
  fixed.push(`solver = ${config.solver ?? "noninteracting"}`);
  fixed.push(
    `lattice = ${config.lattice?.nx ?? "?"}x${config.lattice?.ny ?? "?"} ${config.lattice?.kind ?? "square"}`,
  );
  if (!selectedPath.startsWith("interaction.")) {
    fixed.push(
      `pairing_channel = ${config.interaction?.pairing_channel ?? "none"}`,
    );
  }
  if (!selectedPath.startsWith("drive.")) {
    fixed.push(`drive.amplitude_x = ${config.drive?.amplitude_x ?? 0}`);
  }
  if (!selectedPath.startsWith("time.") && !selectedPath.startsWith("adaptive.")) {
    fixed.push(`dt = ${config.time?.dt ?? 0.1}`);
  }
  return fixed;
}

function parseValues(valuesStr: string): number[] {
  return valuesStr
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map(Number)
    .filter((n) => Number.isFinite(n));
}

export function SweepRailPanel(props: SweepRailPanelProps) {
  const { draftConfig, baselinePresetName } = props;

  const [selectedPath, setSelectedPath] = useState<SweepablePath>(
    "drive.amplitude_x",
  );
  const [valuesStr, setValuesStr] = useState("0.1, 0.2, 0.5, 1.0");

  const parameterKind = inferParameterKind(selectedPath);
  const baselineValue = resolveBaselineValue(draftConfig, selectedPath);
  const parsedValues = useMemo(() => parseValues(valuesStr), [valuesStr]);
  const sweepPointCount = parsedValues.length;
  const fixedAxes = useMemo(
    () => describeFixedAxes(draftConfig, selectedPath),
    [draftConfig, selectedPath],
  );

  const guardrails = [
    "Keep sweep axis kind (physics vs numerical) explicit so mixed scans do not blur hypothesis and convergence reads.",
    "Fix all axes except the swept parameter so the scan reads as a controlled 1D slice.",
    ...SWEEP_TEMPLATES.map((t) => `Template: ${t}`),
  ];

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Sweep Definition</p>
          <h2>Sweep Axis</h2>
        </div>
        <span className="signal-badge">{parameterKind}</span>
      </div>

      <p className="state-banner state-warning">
        Planning-only state. Sweep APIs and managed scan artifacts are not yet
        available. Use this panel to frame the sweep axis and point count before
        backend support lands.
      </p>

      <div className="sidebar-stack">
        <article className="sidebar-card">
          <span className="sidebar-card-label">Parameter Path</span>
          <div className="sidebar-card-value">
            <select
              className="field"
              value={selectedPath}
              onChange={(e) =>
                setSelectedPath(e.target.value as SweepablePath)
              }
            >
              {SWEEPABLE_PATHS.map((path) => (
                <option key={path} value={path}>
                  {path}
                </option>
              ))}
            </select>
          </div>
          <p className="sidebar-card-copy">
            Select the parameter to sweep. The kind label updates automatically
            based on whether the path targets physics or numerical controls.
          </p>
        </article>

        <article className="sidebar-card">
          <span className="sidebar-card-label">Parameter Kind</span>
          <strong className="sidebar-card-value">{parameterKind}</strong>
          <p className="sidebar-card-copy">
            {parameterKind === "numerical"
              ? "This path controls solver numerics. A sweep here reads as a convergence or sensitivity check."
              : "This path controls physical parameters. A sweep here reads as a hypothesis-facing physics scan."}
          </p>
        </article>

        <article className="sidebar-card">
          <span className="sidebar-card-label">Values</span>
          <div className="sidebar-card-value">
            <input
              type="text"
              className="field"
              value={valuesStr}
              onChange={(e) => setValuesStr(e.target.value)}
              placeholder="0.1, 0.2, 0.5, 1.0"
            />
          </div>
          <p className="sidebar-card-copy">
            Comma-separated list of sweep point values. Each value generates one
            run with the selected parameter set accordingly.
          </p>
        </article>

        <article className="sidebar-card">
          <span className="sidebar-card-label">Baseline Value</span>
          <strong className="sidebar-card-value">
            {baselineValue}
            {baselinePresetName ? (
              <span style={{ fontWeight: "normal", marginLeft: "0.5em", opacity: 0.7 }}>
                (from {baselinePresetName})
              </span>
            ) : null}
          </strong>
          <p className="sidebar-card-copy">
            Current value of <code>{selectedPath}</code> in the active draft
            config. The sweep will produce runs that deviate from this baseline.
          </p>
        </article>

        <article className="sidebar-card">
          <span className="sidebar-card-label">Fixed Axes</span>
          <div className="sidebar-card-value">
            {fixedAxes.map((axis) => (
              <p key={axis} style={{ margin: 0, fontSize: "0.85em" }}>
                {axis}
              </p>
            ))}
          </div>
          <p className="sidebar-card-copy">
            These parameters remain constant across all sweep points. Only the
            selected parameter path varies.
          </p>
        </article>
      </div>

      <div className="panel-subheader">
        <h3>Sweep Point Count</h3>
      </div>

      <div className="sidebar-stack">
        <article className="sidebar-card">
          <span className="sidebar-card-label">Runs to create</span>
          <strong className="sidebar-card-value">
            {sweepPointCount} run{sweepPointCount !== 1 ? "s" : ""}
          </strong>
          <p className="sidebar-card-copy">
            {sweepPointCount === 0
              ? "Enter comma-separated numeric values above to define sweep points."
              : `This sweep will produce ${sweepPointCount} individual run${sweepPointCount !== 1 ? "s" : ""}, each with a different value of ${selectedPath}.`}
          </p>
        </article>
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
