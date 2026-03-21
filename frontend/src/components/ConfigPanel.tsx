import type { ReactNode } from "react";

import type { SimulationConfigInput } from "../api/types";
import { DriveWaveformChart } from "./DriveWaveformChart";
import { CollapsibleSection } from "./ui/CollapsibleSection";
import {
  createDefaultConfig,
  K_SPACE_COMPATIBLE_SELF_ENERGIES,
  SUPPORTED_KBE_SELF_ENERGIES,
  SUPPORTED_OBSERVABLES,
  SUPPORTED_PAIRING_CHANNELS,
  SUPPORTED_REPRESENTATIONS,
  SUPPORTED_SOLVERS,
} from "../lib/defaultConfig";
import type {
  AdaptiveConfigInput,
  DriveConfigInput,
  InitialStateConfigInput,
  InteractionConfigInput,
  KbeConfigInput,
  ThermalBranchConfigInput,
} from "../lib/defaultConfig";

type ConfigPanelProps = {
  config: SimulationConfigInput;
  disabled: boolean;
  onConfigChange: (next: SimulationConfigInput) => void;
  onReset: () => void;
};

type FieldProps = {
  label: string;
  children: ReactNode;
  hint?: string;
};

export function ConfigPanel(props: ConfigPanelProps) {
  const { config, disabled, onConfigChange, onReset } = props;
  const defaults = createDefaultConfig();
  const driveDefaults = defaults.drive as DriveConfigInput;
  const interactionDefaults = defaults.interaction as InteractionConfigInput;
  const initialStateDefaults = defaults.initial_state as InitialStateConfigInput;
  const kbeDefaults = defaults.kbe as KbeConfigInput;
  const adaptiveDefaults = defaults.adaptive as AdaptiveConfigInput;
  const thermalBranchDefaults = defaults.thermal_branch as ThermalBranchConfigInput;
  const drive: DriveConfigInput = (config.drive ?? driveDefaults) as DriveConfigInput;
  const interaction: InteractionConfigInput = (config.interaction ?? interactionDefaults) as InteractionConfigInput;
  const initialState: InitialStateConfigInput = (config.initial_state ?? initialStateDefaults) as InitialStateConfigInput;
  const kbe: KbeConfigInput = (config.kbe ?? kbeDefaults) as KbeConfigInput;
  const adaptive: AdaptiveConfigInput = (config.adaptive ?? adaptiveDefaults) as AdaptiveConfigInput;
  const thermalBranch: ThermalBranchConfigInput = (config.thermal_branch ?? thermalBranchDefaults) as ThermalBranchConfigInput;
  const observables = new Set(config.observables ?? defaults.observables ?? []);
  const showKbeControls = (config.solver ?? "noninteracting") === "kbe_hfb";
  const representation = config.representation ?? "real_space";
  const kbeSelfEnergy = kbe.self_energy ?? "hfb";
  const kSpaceIncompatible =
    representation === "k_space" &&
    (config.solver ?? "noninteracting") === "kbe_hfb" &&
    !(K_SPACE_COMPATIBLE_SELF_ENERGIES as readonly string[]).includes(kbeSelfEnergy);
  const kSpaceNeedsPeriodicBoundary =
    representation === "k_space" && (config.lattice.boundary ?? "periodic") !== "periodic";

  function updateTopLevel<K extends keyof SimulationConfigInput>(key: K, value: SimulationConfigInput[K]) {
    onConfigChange({
      ...config,
      [key]: value,
    });
  }

  function updateSolver(value: SimulationConfigInput["solver"]) {
    const nextObservables = new Set(observables);
    const nextInteraction: InteractionConfigInput = { ...interaction };
    const nextInitialState: InitialStateConfigInput = { ...initialState };

    if (value !== "noninteracting") {
      nextObservables.add("pairing");
      nextObservables.add("pairing_s");
      nextObservables.add("pairing_d");
      if ((nextInteraction.pairing_channel ?? "none") === "none") {
        nextInteraction.pairing_channel = "bond_d";
      }
      if ((nextInitialState.seed_pairing ?? 0) === 0) {
        nextInitialState.seed_pairing = 0.2;
      }
    }

    onConfigChange({
      ...config,
      solver: value,
      interaction: nextInteraction,
      initial_state: nextInitialState,
      observables: SUPPORTED_OBSERVABLES.filter((name) => nextObservables.has(name)),
    });
  }

  function updateLattice<K extends keyof SimulationConfigInput["lattice"]>(
    key: K,
    value: SimulationConfigInput["lattice"][K],
  ) {
    onConfigChange({
      ...config,
      lattice: {
        ...config.lattice,
        [key]: value,
      },
    });
  }

  function updateTime<K extends keyof SimulationConfigInput["time"]>(
    key: K,
    value: SimulationConfigInput["time"][K],
  ) {
    onConfigChange({
      ...config,
      time: {
        ...config.time,
        [key]: value,
      },
    });
  }

  function updateDrive<K extends keyof NonNullable<SimulationConfigInput["drive"]>>(
    key: K,
    value: NonNullable<SimulationConfigInput["drive"]>[K],
  ) {
    onConfigChange({
      ...config,
      drive: {
        ...drive,
        [key]: value,
      },
    });
  }

  function updateInteraction<K extends keyof NonNullable<SimulationConfigInput["interaction"]>>(
    key: K,
    value: NonNullable<SimulationConfigInput["interaction"]>[K],
  ) {
    onConfigChange({
      ...config,
      interaction: {
        ...interaction,
        [key]: value,
      },
    });
  }

  function updateInitialState<K extends keyof NonNullable<SimulationConfigInput["initial_state"]>>(
    key: K,
    value: NonNullable<SimulationConfigInput["initial_state"]>[K],
  ) {
    onConfigChange({
      ...config,
      initial_state: {
        ...initialState,
        [key]: value,
      },
    });
  }

  function updateObservable(name: string, checked: boolean) {
    const next = new Set(observables);
    if (checked) {
      next.add(name);
    } else if (next.size > 1) {
      next.delete(name);
    }

    onConfigChange({
      ...config,
      observables: Array.from(next),
    });
  }

  function updateKbe<K extends keyof NonNullable<SimulationConfigInput["kbe"]>>(
    key: K,
    value: NonNullable<SimulationConfigInput["kbe"]>[K],
  ) {
    onConfigChange({
      ...config,
      kbe: {
        ...kbe,
        [key]: value,
      },
    });
  }

  function updateAdaptive<K extends keyof NonNullable<SimulationConfigInput["adaptive"]>>(
    key: K,
    value: NonNullable<SimulationConfigInput["adaptive"]>[K],
  ) {
    onConfigChange({
      ...config,
      adaptive: {
        ...adaptive,
        [key]: value,
      },
    });
  }

  function updateThermalBranch<K extends keyof NonNullable<SimulationConfigInput["thermal_branch"]>>(
    key: K,
    value: NonNullable<SimulationConfigInput["thermal_branch"]>[K],
  ) {
    onConfigChange({
      ...config,
      thermal_branch: {
        ...thermalBranch,
        [key]: value,
      },
    });
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Draft</p>
          <h2>Simulation Draft</h2>
        </div>
        <button type="button" className="ghost-button" onClick={onReset} disabled={disabled}>
          Reset Draft
        </button>
      </div>

      <div className="panel-grid">
        <Field label="Run Name">
          <input
            aria-label="Run Name"
            value={config.name ?? ""}
            onChange={(event) => updateTopLevel("name", event.target.value || null)}
            disabled={disabled}
            placeholder="square-4x4-baseline"
          />
        </Field>
        <Field label="Solver" hint="Current backend implementation">
          <select
            aria-label="Solver"
            value={config.solver ?? "noninteracting"}
            onChange={(event) => updateSolver(event.target.value as SimulationConfigInput["solver"])}
            disabled={disabled}
          >
            {SUPPORTED_SOLVERS.map((solver) => (
              <option key={solver} value={solver}>
                {solver}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Representation" hint="k_space: periodic square lattice only">
          <select
            aria-label="Representation"
            value={representation}
            onChange={(event) =>
              updateTopLevel("representation", event.target.value as SimulationConfigInput["representation"])
            }
            disabled={disabled}
          >
            {SUPPORTED_REPRESENTATIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {kSpaceNeedsPeriodicBoundary && (
        <p className="field-hint" style={{ color: "var(--color-warning, #b45309)", marginBottom: "0.5rem" }}>
          k_space requires periodic boundary condition.
        </p>
      )}
      {kSpaceIncompatible && (
        <p className="field-hint" style={{ color: "var(--color-warning, #b45309)", marginBottom: "0.5rem" }}>
          k_space is not supported with self_energy={kbeSelfEnergy}. Only hfb is supported in k-space.
        </p>
      )}

      <CollapsibleSection title="Lattice" defaultOpen={true}>
        <div className="panel-grid panel-grid-3">
          <Field label="Nx">
            <input
              type="number"
              min={2}
              step={1}
              value={config.lattice.nx}
              onChange={(event) => updateLattice("nx", parseInteger(event.target.value, config.lattice.nx))}
              disabled={disabled}
            />
          </Field>
          <Field label="Ny">
            <input
              type="number"
              min={2}
              step={1}
              value={config.lattice.ny}
              onChange={(event) => updateLattice("ny", parseInteger(event.target.value, config.lattice.ny))}
              disabled={disabled}
            />
          </Field>
          <Field label="Boundary">
            <select
              value={config.lattice.boundary ?? "periodic"}
              onChange={(event) =>
                updateLattice("boundary", event.target.value as SimulationConfigInput["lattice"]["boundary"])
              }
              disabled={disabled}
            >
              <option value="periodic">periodic</option>
              <option value="open">open</option>
            </select>
          </Field>
          <Field label="Hopping t">
            <input
              type="number"
              step="0.1"
              value={config.lattice.hopping ?? 1.0}
              onChange={(event) =>
                updateLattice("hopping", parseNumber(event.target.value, config.lattice.hopping ?? 1.0))
              }
              disabled={disabled}
            />
          </Field>
          <Field label="Chemical Potential">
            <input
              type="number"
              step="0.1"
              value={config.lattice.chemical_potential ?? 0.0}
              onChange={(event) =>
                updateLattice(
                  "chemical_potential",
                  parseNumber(event.target.value, config.lattice.chemical_potential ?? 0.0),
                )
              }
              disabled={disabled}
            />
          </Field>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Time Grid" defaultOpen={true}>
        <div className="panel-grid panel-grid-3">
          <Field label="t_final">
            <input
              type="number"
              step="0.1"
              value={config.time.t_final}
              onChange={(event) => updateTime("t_final", parseNumber(event.target.value, config.time.t_final))}
              disabled={disabled}
            />
          </Field>
          <Field label="dt">
            <input
              type="number"
              step="0.01"
              value={config.time.dt}
              onChange={(event) => updateTime("dt", parseNumber(event.target.value, config.time.dt))}
              disabled={disabled}
            />
          </Field>
          <Field label="save_every">
            <input
              type="number"
              min={1}
              step={1}
              value={config.time.save_every ?? 1}
              onChange={(event) => updateTime("save_every", parseInteger(event.target.value, config.time.save_every ?? 1))}
              disabled={disabled}
            />
          </Field>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Drive" defaultOpen={false}>
        <div className="panel-grid panel-grid-3">
          <Field label="Waveform type">
            <select
              value={drive.drive_type ?? "gaussian"}
              onChange={(event) => updateDrive("drive_type", event.target.value as "gaussian" | "sine" | "sech2" | "trapezoid")}
              disabled={disabled}
            >
              <option value="gaussian">Gaussian pulse</option>
              <option value="sine">Pure sinusoidal</option>
              <option value="sech2">Sech² pulse</option>
              <option value="trapezoid">Trapezoid pulse</option>
            </select>
          </Field>
          <Field label="A_x amplitude">
            <input
              type="number"
              step="0.05"
              value={drive.amplitude_x ?? 0}
              onChange={(event) => updateDrive("amplitude_x", parseNumber(event.target.value, drive.amplitude_x ?? 0))}
              disabled={disabled}
            />
          </Field>
          <Field label="A_y amplitude">
            <input
              type="number"
              step="0.05"
              value={drive.amplitude_y ?? 0}
              onChange={(event) => updateDrive("amplitude_y", parseNumber(event.target.value, drive.amplitude_y ?? 0))}
              disabled={disabled}
            />
          </Field>
          <Field label="Frequency">
            <input
              type="number"
              step="0.1"
              value={drive.frequency ?? 0}
              onChange={(event) => updateDrive("frequency", parseNumber(event.target.value, drive.frequency ?? 0))}
              disabled={disabled}
            />
          </Field>
          <Field label="Phase">
            <input
              type="number"
              step="0.1"
              value={drive.phase ?? 0}
              onChange={(event) => updateDrive("phase", parseNumber(event.target.value, drive.phase ?? 0))}
              disabled={disabled}
            />
          </Field>
          <Field label="Center">
            <input
              type="number"
              step="0.1"
              value={drive.center ?? 0}
              onChange={(event) => updateDrive("center", parseNumber(event.target.value, drive.center ?? 0))}
              disabled={disabled}
            />
          </Field>
          <Field label="Width">
            <input
              type="number"
              min={0.01}
              step="0.05"
              value={drive.width ?? 1}
              onChange={(event) => updateDrive("width", parseNumber(event.target.value, drive.width ?? 1))}
              disabled={disabled}
            />
          </Field>
        </div>
        <DriveWaveformChart drive={drive} tFinal={config.time.t_final ?? 5} />
      </CollapsibleSection>

      <CollapsibleSection title="Interaction and Initial State" defaultOpen={false}>
        <div className="panel-grid panel-grid-3">
          <Field label="Onsite U" hint="Reserved for future solvers">
            <input
              type="number"
              step="0.1"
              value={interaction.onsite_u ?? 0}
              onChange={(event) =>
                updateInteraction("onsite_u", parseNumber(event.target.value, interaction.onsite_u ?? 0))
              }
              disabled={disabled}
            />
          </Field>
          <Field label="Nearest-neighbor V">
            <input
              type="number"
              step="0.1"
              value={interaction.nearest_neighbor_v ?? 0}
              onChange={(event) =>
                updateInteraction(
                  "nearest_neighbor_v",
                  parseNumber(event.target.value, interaction.nearest_neighbor_v ?? 0),
                )
              }
              disabled={disabled}
            />
          </Field>
          <Field label="Pairing Channel" hint="TDHFB / KBE-HFB selection">
            <select
              aria-label="Pairing Channel"
              value={interaction.pairing_channel ?? "none"}
              onChange={(event) =>
                updateInteraction("pairing_channel", event.target.value as NonNullable<SimulationConfigInput["interaction"]>["pairing_channel"])
              }
              disabled={disabled}
            >
              {SUPPORTED_PAIRING_CHANNELS.map((channel) => (
                <option key={channel} value={channel}>
                  {channel}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Filling">
            <input
              type="number"
              min={0}
              max={1}
              step="0.05"
              value={initialState.filling ?? 0.5}
              onChange={(event) =>
                updateInitialState("filling", parseNumber(event.target.value, initialState.filling ?? 0.5))
              }
              disabled={disabled}
            />
          </Field>
          <Field label="Temperature">
            <input
              type="number"
              min={0}
              step="0.01"
              value={initialState.temperature ?? 0}
              onChange={(event) =>
                updateInitialState("temperature", parseNumber(event.target.value, initialState.temperature ?? 0))
              }
              disabled={disabled}
            />
          </Field>
          <Field label="Seed Pairing" hint="Weak source field for paired solvers">
            <input
              aria-label="Seed Pairing"
              type="number"
              step="0.01"
              value={initialState.seed_pairing ?? 0}
              onChange={(event) =>
                updateInitialState("seed_pairing", parseNumber(event.target.value, initialState.seed_pairing ?? 0))
              }
              disabled={disabled}
            />
          </Field>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Observables" defaultOpen={false}>
        <div className="checkbox-grid">
          {SUPPORTED_OBSERVABLES.map((name) => {
            const checked = observables.has(name);
            return (
              <label key={name} className="checkbox-card">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(event) => updateObservable(name, event.target.checked)}
                  disabled={disabled || (checked && observables.size === 1)}
                />
                <span>{name}</span>
              </label>
            );
          })}
        </div>
      </CollapsibleSection>

      {showKbeControls ? (
        <CollapsibleSection title="KBE Extensions" defaultOpen={true}>
          <div className="panel-grid panel-grid-3">
            <Field label="KBE Self-Energy" hint="Phase E1 closure">
              <select
                aria-label="KBE Self-Energy"
                value={kbe.self_energy ?? "hfb"}
                onChange={(event) =>
                  updateKbe(
                    "self_energy",
                    event.target.value as NonNullable<SimulationConfigInput["kbe"]>["self_energy"],
                  )
                }
                disabled={disabled}
              >
                {SUPPORTED_KBE_SELF_ENERGIES.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Fixed-Point Iterations">
              <input
                type="number"
                min={1}
                step={1}
                value={kbe.max_fixed_point_iterations ?? 6}
                onChange={(event) =>
                  updateKbe(
                    "max_fixed_point_iterations",
                    parseInteger(event.target.value, kbe.max_fixed_point_iterations ?? 6),
                  )
                }
                disabled={disabled}
              />
            </Field>
            <Field label="Fixed-Point Mixing">
              <input
                type="number"
                min={0.01}
                max={1}
                step="0.05"
                value={kbe.mixing ?? 0.35}
                onChange={(event) => updateKbe("mixing", parseNumber(event.target.value, kbe.mixing ?? 0.35))}
                disabled={disabled}
              />
            </Field>
            <Field label="Tolerance">
              <input
                type="number"
                min={0}
                step="0.0000001"
                value={kbe.tolerance ?? 1e-7}
                onChange={(event) =>
                  updateKbe("tolerance", parseNumber(event.target.value, kbe.tolerance ?? 1e-7))
                }
                disabled={disabled}
              />
            </Field>
            <Field label="Adaptive Step" hint="Phase E2 grid control">
              <input
                aria-label="Adaptive Step"
                type="checkbox"
                checked={adaptive.enabled ?? false}
                onChange={(event) => updateAdaptive("enabled", event.target.checked)}
                disabled={disabled}
              />
            </Field>
            <Field label="Thermal Branch" hint="Phase E3 Matsubara seed">
              <input
                aria-label="Thermal Branch"
                type="checkbox"
                checked={thermalBranch.enabled ?? false}
                onChange={(event) => updateThermalBranch("enabled", event.target.checked)}
                disabled={disabled}
              />
            </Field>
            <Field label="Adaptive Min dt">
              <input
                type="number"
                min={0}
                step="0.01"
                value={adaptive.min_dt ?? ""}
                onChange={(event) =>
                  updateAdaptive("min_dt", parseNullableNumber(event.target.value, adaptive.min_dt ?? null))
                }
                disabled={disabled}
              />
            </Field>
            <Field label="Adaptive Max dt">
              <input
                type="number"
                min={0}
                step="0.01"
                value={adaptive.max_dt ?? ""}
                onChange={(event) =>
                  updateAdaptive("max_dt", parseNullableNumber(event.target.value, adaptive.max_dt ?? null))
                }
                disabled={disabled}
              />
            </Field>
            <Field label="Matsubara Points">
              <input
                type="number"
                min={4}
                step={1}
                value={thermalBranch.n_tau ?? 16}
                onChange={(event) =>
                  updateThermalBranch("n_tau", parseInteger(event.target.value, thermalBranch.n_tau ?? 16))
                }
                disabled={disabled}
              />
            </Field>
          </div>
        </CollapsibleSection>
      ) : null}
    </section>
  );
}

function Field(props: FieldProps) {
  const { label, children, hint } = props;
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <small className="field-hint">{hint}</small> : null}
    </label>
  );
}

function parseNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseNullableNumber(value: string, fallback: number | null): number | null {
  if (value.trim() === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
