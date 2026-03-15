import type { SimulationConfigInput } from "../api/types";

export const SUPPORTED_SOLVERS = ["noninteracting", "tdhfb", "kbe_hfb"] as const;

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
    observables: [...SUPPORTED_OBSERVABLES],
  };
}
