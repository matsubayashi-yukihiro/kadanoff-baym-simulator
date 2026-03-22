import { describe, expect, it } from "vitest";

import {
  normalizeKSpectralPayload,
  normalizeSweepTrArpesHeatmapPayload,
  normalizeTrArpesPreviewPayload,
} from "./derivedPayload";

describe("derived payload normalization", () => {
  it("accepts current k_spectral payload format", () => {
    const model = normalizeKSpectralPayload({
      energy: [-1, 0, 1],
      intensity: [
        [1, 2, 3],
        [4, 5, 6],
      ],
      k_surface: {
        kind: "k_path",
        tick_positions: [0, 1],
        tick_labels: ["Gamma", "X"],
      },
    });

    expect(model).not.toBeNull();
    expect(model?.z).toEqual([
      [1, 4],
      [2, 5],
      [3, 6],
    ]);
    expect(model?.xTickText).toEqual(["Gamma", "X"]);
  });

  it("accepts legacy tr_arpes preview format", () => {
    const model = normalizeTrArpesPreviewPayload({
      probe_centers: [0.1, 0.2],
      omega: [-2, 0, 2],
      intensity: [
        [1, 2, 3],
        [4, 5, 6],
      ],
    });

    expect(model).not.toBeNull();
    expect(model?.xAxisTitle).toBe("probe delay");
    expect(model?.z).toEqual([
      [1, 4],
      [2, 5],
      [3, 6],
    ]);
  });

  it("accepts current tr_arpes preview format", () => {
    const model = normalizeTrArpesPreviewPayload({
      energy: [-1, 0, 1],
      intensity: [
        [1, 2, 3],
        [4, 5, 6],
      ],
      k_surface: {
        kind: "k_path",
        tick_positions: [0, 1],
        tick_labels: ["Gamma", "X"],
      },
    });

    expect(model).not.toBeNull();
    expect(model?.xAxisTitle).toBe("k-path index");
    expect(model?.z).toEqual([
      [1, 4],
      [2, 5],
      [3, 6],
    ]);
  });

  it("accepts current sweep heatmap format", () => {
    const model = normalizeSweepTrArpesHeatmapPayload({
      parameter_values: [0.05, 0.15],
      energy: [-1, 0, 1],
      intensity: [
        [1, 2, 3],
        [4, 5, 6],
      ],
    });

    expect(model).not.toBeNull();
    expect(model?.x).toEqual(["0.05", "0.15"]);
    expect(model?.z).toEqual([
      [1, 4],
      [2, 5],
      [3, 6],
    ]);
  });
});
