import { describe, expect, it } from "vitest";
import { countAnomalies, groupDiagnostics } from "./diagnosticGroups";

describe("groupDiagnostics", () => {
  it("groups keys by pattern and catches anomalies", () => {
    const diagnostics = {
      residual: 0.5,
      solver: "kbe_hfb",
      dt: 0.01,
      rejected_steps: 3,
      custom_field: "ok",
    };
    const groups = groupDiagnostics(diagnostics);
    expect(groups.length).toBeGreaterThanOrEqual(2);

    const convergence = groups.find((g) => g.key === "kbe_convergence");
    expect(convergence).toBeDefined();
    expect(convergence!.entries.some((e) => e.key === "residual" && e.anomalous)).toBe(true);

    const adaptive = groups.find((g) => g.key === "adaptive");
    expect(adaptive).toBeDefined();
    expect(adaptive!.entries.some((e) => e.key === "rejected_steps" && e.anomalous)).toBe(true);

    const other = groups.find((g) => g.key === "other");
    expect(other).toBeDefined();
    expect(other!.entries.some((e) => e.key === "custom_field")).toBe(true);
  });

  it("returns empty array for empty diagnostics", () => {
    expect(groupDiagnostics({})).toEqual([]);
  });

  it("detects NaN/Inf as anomalous", () => {
    const groups = groupDiagnostics({ some_value: NaN });
    expect(countAnomalies(groups)).toBe(1);
  });

  it("detects failure strings as anomalous", () => {
    const groups = groupDiagnostics({ solver: "diverged" });
    expect(countAnomalies(groups)).toBe(1);
  });
});
