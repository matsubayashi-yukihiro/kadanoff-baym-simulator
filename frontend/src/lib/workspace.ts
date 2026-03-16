import type { RunDetail, SimulationConfigInput } from "../api/types";
import {
  SUPPORTED_KBE_SELF_ENERGIES,
  SUPPORTED_PAIRING_CHANNELS,
  SUPPORTED_SOLVERS,
  createDefaultConfig,
} from "./defaultConfig";

export type WorkspaceJob = {
  id: string;
  title: string;
  config: SimulationConfigInput;
  lastRunId: string | null;
  runHistory: string[];
  plotEnabled: boolean;
};

export type JobColumnKind = "text" | "float" | "integer" | "enum" | "boolean";

export type JobColumn = {
  id: string;
  label: string;
  kind: JobColumnKind;
  path?: string;
  nullable?: boolean;
  options?: readonly string[];
};

export type WorkspaceSnapshot = {
  jobs: WorkspaceJob[];
  activeJobId: string | null;
};

export const JOB_PARAMETER_COLUMNS: JobColumn[] = [
  { id: "solver", label: "Solver", kind: "enum", path: "solver", options: SUPPORTED_SOLVERS },
  { id: "lattice.nx", label: "Nx", kind: "integer", path: "lattice.nx" },
  { id: "lattice.ny", label: "Ny", kind: "integer", path: "lattice.ny" },
  { id: "lattice.boundary", label: "Boundary", kind: "enum", path: "lattice.boundary", options: ["periodic", "open"] },
  { id: "lattice.hopping", label: "Hopping", kind: "float", path: "lattice.hopping" },
  {
    id: "lattice.chemical_potential",
    label: "Chemical Potential",
    kind: "float",
    path: "lattice.chemical_potential",
  },
  { id: "time.t_final", label: "t Final", kind: "float", path: "time.t_final" },
  { id: "time.dt", label: "Time Dt", kind: "float", path: "time.dt" },
  { id: "time.save_every", label: "Save Every", kind: "integer", path: "time.save_every" },
  { id: "drive.amplitude_x", label: "Drive Ax", kind: "float", path: "drive.amplitude_x" },
  { id: "drive.amplitude_y", label: "Drive Ay", kind: "float", path: "drive.amplitude_y" },
  { id: "drive.frequency", label: "Drive Frequency", kind: "float", path: "drive.frequency" },
  { id: "drive.phase", label: "Drive Phase", kind: "float", path: "drive.phase" },
  { id: "drive.center", label: "Drive Center", kind: "float", path: "drive.center" },
  { id: "drive.width", label: "Drive Width", kind: "float", path: "drive.width" },
  { id: "interaction.onsite_u", label: "Onsite U", kind: "float", path: "interaction.onsite_u" },
  {
    id: "interaction.nearest_neighbor_v",
    label: "Nearest V",
    kind: "float",
    path: "interaction.nearest_neighbor_v",
  },
  {
    id: "interaction.pairing_channel",
    label: "Pairing Channel",
    kind: "enum",
    path: "interaction.pairing_channel",
    options: SUPPORTED_PAIRING_CHANNELS,
  },
  { id: "initial_state.filling", label: "Filling", kind: "float", path: "initial_state.filling" },
  { id: "initial_state.temperature", label: "Temperature", kind: "float", path: "initial_state.temperature" },
  { id: "initial_state.seed_pairing", label: "Seed Pairing", kind: "float", path: "initial_state.seed_pairing" },
  {
    id: "kbe.self_energy",
    label: "Self Energy",
    kind: "enum",
    path: "kbe.self_energy",
    options: SUPPORTED_KBE_SELF_ENERGIES,
  },
  {
    id: "kbe.max_fixed_point_iterations",
    label: "FP Iterations",
    kind: "integer",
    path: "kbe.max_fixed_point_iterations",
  },
  { id: "kbe.tolerance", label: "KBE Tol", kind: "float", path: "kbe.tolerance" },
  { id: "kbe.mixing", label: "KBE Mixing", kind: "float", path: "kbe.mixing" },
  { id: "kbe.memory_window", label: "Memory Window", kind: "integer", path: "kbe.memory_window", nullable: true },
  { id: "adaptive.enabled", label: "Adaptive", kind: "boolean", path: "adaptive.enabled" },
  { id: "adaptive.atol", label: "Adaptive Atol", kind: "float", path: "adaptive.atol" },
  { id: "adaptive.rtol", label: "Adaptive Rtol", kind: "float", path: "adaptive.rtol" },
  { id: "adaptive.min_dt", label: "Adaptive Min Dt", kind: "float", path: "adaptive.min_dt", nullable: true },
  { id: "adaptive.max_dt", label: "Adaptive Max Dt", kind: "float", path: "adaptive.max_dt", nullable: true },
  { id: "adaptive.max_growth", label: "Max Growth", kind: "float", path: "adaptive.max_growth" },
  { id: "adaptive.min_shrink", label: "Min Shrink", kind: "float", path: "adaptive.min_shrink" },
  { id: "thermal_branch.enabled", label: "Thermal Branch", kind: "boolean", path: "thermal_branch.enabled" },
  { id: "thermal_branch.n_tau", label: "Tau Points", kind: "integer", path: "thermal_branch.n_tau" },
  {
    id: "thermal_branch.max_iterations",
    label: "Thermal Iterations",
    kind: "integer",
    path: "thermal_branch.max_iterations",
  },
  { id: "thermal_branch.mixing", label: "Thermal Mixing", kind: "float", path: "thermal_branch.mixing" },
];

export function createWorkspaceJob(
  existingTitles: string[],
  source?: WorkspaceJob,
): WorkspaceJob {
  const nextConfig = source ? cloneConfig(source.config) : createDefaultConfig();
  const baseTitle = source?.title ?? nextConfig.name ?? "job";
  const title = buildUniqueJobTitle(existingTitles, source ? `${baseTitle} copy` : baseTitle);
  nextConfig.name = title;

  return {
    id: createJobId(),
    title,
    config: nextConfig,
    lastRunId: null,
    runHistory: [],
    plotEnabled: true,
  };
}

export function restoreWorkspaceSnapshot(raw: string | null): WorkspaceSnapshot | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as WorkspaceSnapshot;
    if (!Array.isArray(parsed.jobs) || parsed.jobs.length === 0) {
      return null;
    }
    return {
      jobs: parsed.jobs.map((job) => ({
        ...job,
        title: normalizeTitle(job.title ?? job.config.name ?? "job"),
        config: cloneConfig(job.config),
        lastRunId: job.lastRunId ?? null,
        runHistory: Array.isArray(job.runHistory) ? job.runHistory.filter((value) => typeof value === "string") : [],
        plotEnabled: Boolean(job.plotEnabled),
      })),
      activeJobId: typeof parsed.activeJobId === "string" ? parsed.activeJobId : parsed.jobs[0]?.id ?? null,
    };
  } catch {
    return null;
  }
}

export function snapshotWorkspace(jobs: WorkspaceJob[], activeJobId: string | null): string {
  return JSON.stringify({ jobs, activeJobId });
}

export function getConfigValue(config: SimulationConfigInput, path: string): unknown {
  return path.split(".").reduce<unknown>((current, segment) => {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    return (current as Record<string, unknown>)[segment];
  }, config);
}

export function setConfigValue(
  config: SimulationConfigInput,
  path: string,
  value: unknown,
): SimulationConfigInput {
  const clone = cloneConfig(config) as Record<string, unknown>;
  const segments = path.split(".");
  let cursor: Record<string, unknown> = clone;

  for (const segment of segments.slice(0, -1)) {
    const next = cursor[segment];
    if (!next || typeof next !== "object") {
      cursor[segment] = {};
    }
    cursor = cursor[segment] as Record<string, unknown>;
  }

  cursor[segments[segments.length - 1]] = value;
  return clone as SimulationConfigInput;
}

export function applyJobColumnValue(
  job: WorkspaceJob,
  column: JobColumn,
  value: unknown,
): WorkspaceJob {
  if (column.id === "job_title") {
    return renameJob(job, String(value ?? ""));
  }

  if (!column.path) {
    return job;
  }

  let nextConfig = setConfigValue(job.config, column.path, value);
  if (column.id === "solver" && typeof value === "string") {
    nextConfig = applySolverDefaults(nextConfig, value);
  }

  return {
    ...job,
    config: nextConfig,
  };
}

export function renameJob(job: WorkspaceJob, rawTitle: string): WorkspaceJob {
  const title = normalizeTitle(rawTitle, job.title);
  return {
    ...job,
    title,
    config: {
      ...cloneConfig(job.config),
      name: title,
    },
  };
}

export function computeVisibleParameterColumns(
  jobs: WorkspaceJob[],
  showDifferentOnly: boolean,
  baselineJobId?: string | null,
): JobColumn[] {
  if (!showDifferentOnly || jobs.length <= 1) {
    return JOB_PARAMETER_COLUMNS;
  }

  const baselineJob = jobs.find((job) => job.id === baselineJobId) ?? jobs[0];
  if (!baselineJob) {
    return JOB_PARAMETER_COLUMNS;
  }

  return JOB_PARAMETER_COLUMNS.filter((column) => {
    const path = column.path;
    if (!path) {
      return true;
    }
    const firstValue = serializeColumnValue(getConfigValue(baselineJob.config, path));
    return jobs.some((job) => serializeColumnValue(getConfigValue(job.config, path)) !== firstValue);
  });
}

export function columnValueDiffers(column: JobColumn, job: WorkspaceJob, baseline: WorkspaceJob | null): boolean {
  const path = column.path;
  if (!baseline || !path) {
    return false;
  }

  return (
    serializeColumnValue(getConfigValue(job.config, path)) !==
    serializeColumnValue(getConfigValue(baseline.config, path))
  );
}

export function isTerminalRunState(run: RunDetail["state"]): boolean {
  return run === "succeeded" || run === "failed" || run === "cancelled";
}

export function shortRunId(runId: string | null): string {
  if (!runId) {
    return "-";
  }
  return runId.length <= 10 ? runId : `${runId.slice(0, 8)}…`;
}

function applySolverDefaults(config: SimulationConfigInput, solver: string): SimulationConfigInput {
  if (solver === "noninteracting") {
    return config;
  }

  const observables = new Set(config.observables ?? []);
  observables.add("pairing");
  observables.add("pairing_s");
  observables.add("pairing_d");

  return {
    ...config,
    observables: Array.from(observables),
    interaction: {
      ...config.interaction,
      pairing_channel: config.interaction?.pairing_channel === "none" ? "bond_d" : config.interaction?.pairing_channel,
    },
    initial_state: {
      ...config.initial_state,
      seed_pairing:
        config.initial_state?.seed_pairing === 0 ? 0.2 : (config.initial_state?.seed_pairing ?? 0.2),
    },
  };
}

function serializeColumnValue(value: unknown): string {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toString() : "NaN";
  }
  if (value === null || value === undefined) {
    return "";
  }
  return JSON.stringify(value);
}

function buildUniqueJobTitle(existingTitles: string[], rawBase: string): string {
  const base = normalizeTitle(rawBase);
  if (!existingTitles.includes(base)) {
    return base;
  }

  let index = 2;
  while (existingTitles.includes(`${base} ${index}`)) {
    index += 1;
  }
  return `${base} ${index}`;
}

function normalizeTitle(rawTitle: string, fallback = "job"): string {
  const trimmed = rawTitle.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

function cloneConfig(config: SimulationConfigInput): SimulationConfigInput {
  return JSON.parse(JSON.stringify(config)) as SimulationConfigInput;
}

function createJobId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `job-${Math.random().toString(36).slice(2, 10)}`;
}
