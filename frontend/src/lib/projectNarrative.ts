type SimulationLike = {
  solver?: string | null;
  kbe?: {
    self_energy?: string | null;
  } | null;
};

type NarrativeCard = {
  kicker: string;
  title: string;
  body: string;
};

type WorkflowStep = {
  title: string;
  detail: string;
};

type Guardrail = {
  title: string;
  detail: string;
};

export type TrackTone = "validated" | "partial" | "prototype" | "future";

export type TrackDescriptor = {
  key: string;
  title: string;
  statusLabel: string;
  tone: TrackTone;
  scope: string;
  evidence: string;
  caution?: string;
};

export const PROJECT_PILLARS: NarrativeCard[] = [
  {
    kicker: "Core Platform",
    title: "A shared solver foundation",
    body:
      "The project is building a common platform for driven 2D lattice systems: time-dependent one-body dynamics, Nambu structure, TDHFB/BdG, KBE paths, observables, and validation all live on the same backbone.",
  },
  {
    kicker: "Mainline Baseline",
    title: "Extended Hubbard is the first benchmark",
    body:
      "The first concrete target is the 2D extended Hubbard model with bond pairing in weak-to-intermediate coupling. It is a baseline problem, not the full identity of the project.",
  },
  {
    kicker: "Extension Path",
    title: "Electron-phonon work is part of the design",
    body:
      "The architecture is meant to carry Holstein, SSH, and Hubbard-Holstein studies later without rewriting the console around a one-off model.",
  },
];

export const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    title: "Frame",
    detail: "Keep the Kadanoff-Baym baseline and the current validated scope visible before touching parameters.",
  },
  {
    title: "Draft",
    detail: "Define lattice, drive, interaction, pairing, and contour controls without hiding backend semantics.",
  },
  {
    title: "Launch",
    detail: "Treat each run as a stored artifact with queue state, timestamps, and solver-specific evidence surfaces.",
  },
  {
    title: "Inspect",
    detail: "Read observables, diagnostics, and two-time slices as evidence, not as decoration.",
  },
];

export const VALIDATION_GUARDRAILS: Guardrail[] = [
  {
    title: "Physics validation lives in backend gates",
    detail:
      "Frontend and API tests protect workflow, but they do not replace the unit, invariant, and benchmark criteria in the backend validation spec.",
  },
  {
    title: "Prototype and reference stay separate",
    detail:
      "`second_born` remains a heuristic prototype path. The UI should not present it as a literature-closed second Born solver.",
  },
  {
    title: "Reference scope is still bounded",
    detail:
      "`second_born_reference` is validated within the equal-time GKBA contour-dressed scope. Full contour second Born is still a future target.",
  },
];

export const TRACK_DESCRIPTORS: TrackDescriptor[] = [
  {
    key: "noninteracting",
    title: "Noninteracting One-Body Solver",
    statusLabel: "Validated",
    tone: "validated",
    scope: "Exact one-body propagation with continuity, energy-work balance, and exact 2x2 benchmark gates.",
    evidence: "Use this as the baseline for driven currents, density transport, and dt convergence.",
  },
  {
    key: "tdhfb",
    title: "TDHFB / BdG",
    statusLabel: "Partially Validated",
    tone: "partial",
    scope: "Paired stationary states, generalized-density structure constraints, and the noninteracting limit are covered.",
    evidence: "This is the mean-field bridge to superconducting dynamics and the reference equal-time check for KBE modes.",
  },
  {
    key: "kbe_hfb",
    title: "KBE + HFB",
    statusLabel: "Partially Validated",
    tone: "partial",
    scope: "Equal-time matching to TDHFB, retarded and lesser constraints, and short-window interacting benchmarks are covered.",
    evidence: "Use it to inspect the KBE equal-time path before enabling second-Born scattering closures.",
  },
  {
    key: "second_born",
    title: "KBE + second Born Prototype",
    statusLabel: "Prototype Only",
    tone: "prototype",
    scope: "A heuristic dissipative closure with diagnostics and regression coverage, but not a literature-closed full second Born implementation.",
    evidence: "Useful for exploratory runs, API wiring, and regression comparisons against the reference path.",
    caution: "Do not present this mode as validated many-body physics.",
  },
  {
    key: "second_born_reference",
    title: "KBE + second Born Reference",
    statusLabel: "Validated Scope",
    tone: "validated",
    scope: "Explicit self-energy with equal-time GKBA causal marching plus self-consistent Matsubara and mixed contour dressing.",
    evidence: "This is the current reference path for Phase E within the equal-time GKBA contour-dressed scope.",
    caution: "Validated does not mean full two-time contour second Born is complete.",
  },
  {
    key: "full_contour",
    title: "Full Contour second Born",
    statusLabel: "Future Target",
    tone: "future",
    scope: "The theoretical baseline remains full two-time KBE with conserving self-energy, but that implementation is not yet public here.",
    evidence: "Keep the target visible so the console does not over-claim the current backend.",
  },
];

const TRACKS_BY_KEY = TRACK_DESCRIPTORS.reduce<Record<string, TrackDescriptor>>((registry, track) => {
  registry[track.key] = track;
  return registry;
}, {});

export function getSimulationTrack(config: SimulationLike | null | undefined): TrackDescriptor {
  const solver = config?.solver ?? "noninteracting";

  if (solver === "tdhfb") {
    return TRACKS_BY_KEY.tdhfb;
  }

  if (solver === "kbe_hfb") {
    const selfEnergy = config?.kbe?.self_energy ?? "hfb";

    if (selfEnergy === "second_born") {
      return TRACKS_BY_KEY.second_born;
    }

    if (selfEnergy === "second_born_reference") {
      return TRACKS_BY_KEY.second_born_reference;
    }

    return TRACKS_BY_KEY.kbe_hfb;
  }

  return TRACKS_BY_KEY.noninteracting;
}
