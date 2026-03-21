import { describe, expect, it } from "vitest";

import { cloneConfig, sanitizeSimulationConfig } from "./workbench";

describe("workbench config sanitization", () => {
  it("extracts preset config and drops preset metadata", () => {
    const result = cloneConfig({
      name: "preset-a",
      category: "demo",
      validation_status: "prototype",
      summary: "demo",
      scope_note: "scope",
      primary_observable: "pairing_d",
      config: {
        name: "run-a",
        solver: "kbe_hfb",
        representation: "real_space",
        lattice: { kind: "square", nx: 4, ny: 4, boundary: "periodic", hopping: 1, chemical_potential: 0 },
        time: { t_final: 1, dt: 0.1, save_every: 1 },
        drive: { drive_type: "gaussian", amplitude_x: 0, amplitude_y: 0, frequency: 0, phase: 0, center: 0, width: 1 },
        interaction: { onsite_u: 0, nearest_neighbor_v: 0, pairing_channel: "bond_d" },
        initial_state: { filling: 0.5, temperature: 0, seed_pairing: 0.2 },
        kbe: { self_energy: "hfb", max_fixed_point_iterations: 6, tolerance: 1e-7, mixing: 0.35, memory_window: null },
        adaptive: { enabled: false, atol: 1e-7, rtol: 1e-5, min_dt: null, max_dt: null, max_growth: 2, min_shrink: 0.25 },
        thermal_branch: { enabled: false, n_tau: 16, max_iterations: 8, mixing: 0.3 },
        observables: ["pairing_d"],
      },
    });

    expect(result.name).toBe("run-a");
    expect("category" in result).toBe(false);
    expect("summary" in result).toBe(false);
  });

  it("drops stray top-level preset fields from persisted draft config", () => {
    const result = sanitizeSimulationConfig({
      name: "run-b",
      solver: "noninteracting",
      representation: "real_space",
      category: "demo",
      validation_status: "prototype",
      summary: "demo",
      lattice: { kind: "square", nx: 4, ny: 4, boundary: "periodic", hopping: 1, chemical_potential: 0 },
      time: { t_final: 1, dt: 0.1, save_every: 1 },
      drive: { drive_type: "gaussian", amplitude_x: 0, amplitude_y: 0, frequency: 0, phase: 0, center: 0, width: 1 },
      interaction: { onsite_u: 0, nearest_neighbor_v: 0, pairing_channel: "none" },
      initial_state: { filling: 0.5, temperature: 0, seed_pairing: 0 },
      kbe: { self_energy: "hfb", max_fixed_point_iterations: 6, tolerance: 1e-7, mixing: 0.35, memory_window: null },
      adaptive: { enabled: false, atol: 1e-7, rtol: 1e-5, min_dt: null, max_dt: null, max_growth: 2, min_shrink: 0.25 },
      thermal_branch: { enabled: false, n_tau: 16, max_iterations: 8, mixing: 0.3 },
      observables: ["density"],
    });

    expect(result.name).toBe("run-b");
    expect("category" in result).toBe(false);
    expect("validation_status" in result).toBe(false);
    expect("summary" in result).toBe(false);
  });
});
