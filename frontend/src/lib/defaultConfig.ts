import type { SimulationConfigInput } from "../api/types";

export type DriveConfigInput = NonNullable<SimulationConfigInput["drive"]>;
export type InteractionConfigInput = NonNullable<SimulationConfigInput["interaction"]>;
export type InitialStateConfigInput = NonNullable<SimulationConfigInput["initial_state"]>;
export type EquilibriumConfigInput = NonNullable<SimulationConfigInput["equilibrium"]>;
export type KbeConfigInput = NonNullable<SimulationConfigInput["kbe"]>;
export type AdaptiveConfigInput = NonNullable<SimulationConfigInput["adaptive"]>;
export type ThermalBranchConfigInput = NonNullable<SimulationConfigInput["thermal_branch"]>;

export const SUPPORTED_SOLVERS = ["noninteracting", "tdhfb", "kbe_hfb"] as const;
export const SUPPORTED_KBE_SELF_ENERGIES = ["hfb", "second_born", "second_born_reference"] as const;
export const SUPPORTED_REPRESENTATIONS = ["real_space", "k_space"] as const;

// k_space requires periodic boundary and specific solver/self_energy combos
export const K_SPACE_COMPATIBLE_SELF_ENERGIES = ["hfb"] as const;

export const SUPPORTED_PAIRING_CHANNELS = ["none", "onsite", "bond_s", "bond_d"] as const;

export const SUPPORTED_OBSERVABLES = [
  "density",
  "current_x",
  "current_y",
  "energy",
  "vector_potential",
  "pairing",
  "pairing_s",
  "pairing_d",
] as const;

export function createDefaultConfig(): SimulationConfigInput {
  return {
    name: "square-4x4-baseline",
    solver: "noninteracting",
    representation: "real_space",
    lattice: {
      kind: "square",
      nx: 4,
      ny: 4,
      boundary: "periodic",
      hopping: 1.0,
      chemical_potential: 0.0,
    },
    time: {
      t_final: 1.0,
      dt: 0.1,
      save_every: 1,
    },
    drive: {
      drive_type: "gaussian" as const,
      amplitude_x: 0.25,
      amplitude_y: 0.0,
      frequency: 3.0,
      phase: 0.0,
      center: 0.5,
      width: 0.3,
    },
    interaction: {
      onsite_u: 0.0,
      nearest_neighbor_v: 0.0,
      pairing_channel: "none",
    },
    initial_state: {
      filling: 0.5,
      temperature: 0.0,
      seed_pairing: 0.0,
    },
    equilibrium: {
      method: "auto" as const,
      allow_approximation_mismatch: false,
      max_iterations: 192,
      tolerance: 1e-8,
      mixing: 0.22,
    },
    kbe: {
      self_energy: "hfb",
      max_fixed_point_iterations: 6,
      tolerance: 1e-7,
      mixing: 0.35,
      memory_window: null,
    },
    adaptive: {
      enabled: true,
      atol: 1e-7,
      rtol: 1e-5,
      min_dt: null,
      max_dt: null,
      max_growth: 2.0,
      min_shrink: 0.25,
    },
    thermal_branch: {
      enabled: false,
      n_tau: 16,
      max_iterations: 8,
      mixing: 0.3,
    },
    observables: [...SUPPORTED_OBSERVABLES],
  };
}
