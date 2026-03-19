export type DiagnosticEntry = {
  key: string;
  value: unknown;
  anomalous: boolean;
};

export type DiagnosticGroup = {
  key: string;
  label: string;
  entries: DiagnosticEntry[];
};

const GROUP_RULES: Array<{ key: string; label: string; patterns: RegExp[] }> = [
  {
    key: "kbe_convergence",
    label: "KBE Convergence",
    patterns: [/residual/, /fixed_point/, /iterations/, /convergence/, /gkba/],
  },
  {
    key: "adaptive",
    label: "Adaptive Step",
    patterns: [/adaptive/, /dt_effective/, /step_count/, /rejected_steps/],
  },
  {
    key: "thermal",
    label: "Thermal Branch",
    patterns: [/thermal/, /matsubara/, /mixed_branch/, /factorized/],
  },
  {
    key: "self_energy",
    label: "Self-Energy",
    patterns: [/self_energy/, /second_born/, /collision/, /memory_integral/],
  },
  {
    key: "conservation",
    label: "Conservation",
    patterns: [/energy/, /density_conservation/, /continuity/, /mismatch/, /work/],
  },
  {
    key: "solver_info",
    label: "Solver Info",
    patterns: [/solver/, /^dt$/, /site_count/, /scope/, /grid_shape/],
  },
];

export function groupDiagnostics(diagnostics: Record<string, unknown>): DiagnosticGroup[] {
  const entries = Object.entries(diagnostics);
  if (entries.length === 0) return [];

  const assigned = new Set<string>();
  const groups: DiagnosticGroup[] = [];

  for (const rule of GROUP_RULES) {
    const matched: DiagnosticEntry[] = [];
    for (const [key, value] of entries) {
      if (assigned.has(key)) continue;
      if (rule.patterns.some((pattern) => pattern.test(key))) {
        matched.push({ key, value, anomalous: isAnomalous(key, value) });
        assigned.add(key);
      }
    }
    if (matched.length > 0) {
      groups.push({ key: rule.key, label: rule.label, entries: matched });
    }
  }

  const remaining: DiagnosticEntry[] = [];
  for (const [key, value] of entries) {
    if (!assigned.has(key)) {
      remaining.push({ key, value, anomalous: isAnomalous(key, value) });
    }
  }
  if (remaining.length > 0) {
    groups.push({ key: "other", label: "Other", entries: remaining });
  }

  return groups;
}

export function countAnomalies(groups: DiagnosticGroup[]): number {
  let count = 0;
  for (const group of groups) {
    for (const entry of group.entries) {
      if (entry.anomalous) count++;
    }
  }
  return count;
}

function isAnomalous(key: string, value: unknown): boolean {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return true;
    if (key.includes("residual") && Math.abs(value) > 1e-2) return true;
    if (key.includes("mismatch") && Math.abs(value) > 1e-2) return true;
    if (key.includes("rejected_steps") && value > 0) return true;
  }
  if (typeof value === "string") {
    const lower = value.toLowerCase();
    if (lower.includes("fail") || lower.includes("error") || lower.includes("diverge")) return true;
  }
  return false;
}
