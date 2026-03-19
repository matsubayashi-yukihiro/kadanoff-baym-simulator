import type { PresetConfig, SimulationConfigInput } from "../api/types";
import { createDefaultConfig } from "./defaultConfig";
import type {
  DriveConfigInput,
  InitialStateConfigInput,
  InteractionConfigInput,
  KbeConfigInput,
} from "./defaultConfig";
import { getSimulationTrack } from "./projectNarrative";

export type WorkbenchTab = "single-job" | "compare-jobs" | "parameter-sweep";

export type WorkbenchTabDescriptor = {
  key: WorkbenchTab;
  label: string;
  description: string;
  heading: string;
  summary: string;
};

export type WorkingStudy = {
  title: string;
  question: string;
  status: string;
  targetObservables: string[];
  acceptanceChecks: string[];
  scopeNote: string;
};

export type PresetDescriptor = {
  title: string;
  category: string;
  intendedTab: string;
  summary: string;
  scopeNote: string;
};

export type SuggestedRunRole = "baseline" | "candidate" | "control" | "numerical_check";

export type ComparisonKind = "physics_hypothesis" | "numerical_validation" | "regression";

export type BaselineRelation = {
  summary: string;
  suggestedRole: SuggestedRunRole;
  differences: string[];
};

export type ComparisonSummaryRow = {
  label: string;
  value: string;
  code?: boolean;
};

export type ComparisonVariantDescriptor = {
  key: string;
  slot: string;
  label: string;
  badges: string[];
  summary: string;
  detail: string;
  differences: string[];
  active?: boolean;
  planning?: boolean;
};

export type ComparisonPlanningSignal = {
  title: string;
  value: string;
  copy: string;
};

export type ComparisonViewPlaceholder = {
  title: string;
  copy: string;
};

export type ComparisonDraftDescriptor = {
  comparisonKind: ComparisonKind;
  comparisonKindLabel: string;
  comparisonKindReason: string;
  variantIntent: string;
  templateSeed: string;
  baselineName: string;
  planningBanner: string;
  emptyStateTitle: string;
  emptyStateCopy: string;
  emptyStateSteps: string[];
  summaryRows: ComparisonSummaryRow[];
  variants: ComparisonVariantDescriptor[];
  planningSignals: ComparisonPlanningSignal[];
  reservedViews: ComparisonViewPlaceholder[];
  guardrails: string[];
};

export const HIGGS_DEMO_PRESET_NAME = "square-4x4-higgs-demo-kbe-hfb";
export const HIGGS_DEMO_PRIMARY_OBSERVABLE = "pairing_d";

type ConfigLike = {
  name?: string | null;
  solver?: string | null;
  lattice?: {
    nx?: number | null;
    ny?: number | null;
  } | null;
  time?: {
    dt?: number | null;
  } | null;
  drive?: {
    amplitude_x?: number | null;
    frequency?: number | null;
  } | null;
  interaction?: {
    pairing_channel?: string | null;
  } | null;
  kbe?: {
    self_energy?: string | null;
  } | null;
  adaptive?: {
    enabled?: boolean | null;
  } | null;
};

type DifferenceDescriptor = {
  label: string;
  current: string;
  baseline: string;
  numerical: boolean;
};

export const WORKBENCH_TABS: WorkbenchTabDescriptor[] = [
  {
    key: "single-job",
    label: "Single Job",
    description: "Inspect one run with baseline, diagnostics, and spectrum context.",
    heading: "Single Job Evidence Surface",
    summary: "Launch one run, frame it against the current baseline, and read its stored evidence without mixing in compare or sweep planning.",
  },
  {
    key: "compare-jobs",
    label: "Compare Jobs",
    description: "Promote hypothesis and validation comparisons to backend-managed artifacts.",
    heading: "Compare Jobs Design Surface",
    summary: "Keep run-to-run comparisons on their own page so hypothesis and numerical validation groups do not collapse back into the single-run viewer.",
  },
  {
    key: "parameter-sweep",
    label: "Parameter Sweep",
    description: "Treat 1D physics and numerical scans as first-class work surfaces.",
    heading: "Parameter Sweep Design Surface",
    summary: "Reserve a dedicated page for physics and numerical scans so sweep setup, guardrails, and future heatmap views stay distinct from single-run inspection.",
  },
];

export function getWorkbenchTabDescriptor(tab: WorkbenchTab): WorkbenchTabDescriptor {
  return WORKBENCH_TABS.find((entry) => entry.key === tab) ?? WORKBENCH_TABS[0];
}

export const WORKING_STUDY: WorkingStudy = {
  title: "Higgs-mode reconnaissance",
  question:
    "How does the post-pulse pairing_d response change across the current mean-field, prototype, and reference paths without overstating validation scope?",
  status: "Local shell while studies API is pending",
  targetObservables: ["pairing_d", "energy", "density"],
  acceptanceChecks: [
    "Keep backend validation scope visible while drafting and reviewing runs.",
    "Show how the current run differs from the working bond_d KBE-HFB baseline scaffold.",
    "Keep spectrum preview and contour inspection on the same single-job surface.",
  ],
  scopeNote:
    "This is an interim frontend shell. Durable study, note, and bundle metadata still depend on the experiment registry and related APIs.",
};

export const COMPARE_TEMPLATES = [
  "bond_s vs bond_d",
  "hfb vs second_born vs second_born_reference",
  "drive amplitude discrete variants",
  "dt coarse vs fine",
  "adaptive tolerance loose vs tight",
];

export const SWEEP_TEMPLATES = [
  "drive.amplitude_x as a physics sweep",
  "time.dt as a numerical sweep",
  "adaptive.rtol as a numerical sweep",
  "kbe.memory_window as a numerical sweep",
];

export function createHiggsDemoPreset(): SimulationConfigInput {
  const demo = createDefaultConfig();
  const driveDefaults = createDefaultConfig().drive as DriveConfigInput;
  const interactionDefaults = createDefaultConfig().interaction as InteractionConfigInput;
  const initialStateDefaults = createDefaultConfig().initial_state as InitialStateConfigInput;
  const kbeDefaults = createDefaultConfig().kbe as KbeConfigInput;
  demo.name = HIGGS_DEMO_PRESET_NAME;
  demo.solver = "kbe_hfb";
  demo.time = {
    ...demo.time,
    t_final: 20.0,
    dt: 0.05,
    save_every: 1,
  };
  demo.drive = {
    ...((demo.drive ?? driveDefaults) as DriveConfigInput),
    amplitude_x: 0.25,
    amplitude_y: 0.125,
    frequency: 2.0,
    phase: 0.0,
    center: 3.0,
    width: 1.2,
  };
  demo.interaction = {
    ...((demo.interaction ?? interactionDefaults) as InteractionConfigInput),
    onsite_u: -2.0,
    nearest_neighbor_v: -2.5,
    pairing_channel: "bond_d",
  };
  demo.initial_state = {
    ...((demo.initial_state ?? initialStateDefaults) as InitialStateConfigInput),
    filling: 0.5,
    temperature: 0.0,
    seed_pairing: 0.2,
  };
  demo.kbe = {
    ...((demo.kbe ?? kbeDefaults) as KbeConfigInput),
    self_energy: "hfb",
  };
  demo.observables = ["density", "energy", "vector_potential", "pairing", "pairing_s", "pairing_d"];
  return demo;
}

export function createFallbackPresets(): SimulationConfigInput[] {
  const oneBody = createDefaultConfig();

  const tdhfb = createDefaultConfig();
  const driveDefaults = createDefaultConfig().drive as DriveConfigInput;
  const interactionDefaults = createDefaultConfig().interaction as InteractionConfigInput;
  const initialStateDefaults = createDefaultConfig().initial_state as InitialStateConfigInput;
  tdhfb.name = "square-4x4-bond-d-tdhfb";
  tdhfb.solver = "tdhfb";
  tdhfb.drive = {
    ...((tdhfb.drive ?? driveDefaults) as DriveConfigInput),
    amplitude_x: 0.0,
    amplitude_y: 0.0,
    frequency: 0.0,
    center: 0.0,
    width: 1.0,
  };
  tdhfb.interaction = {
    ...((tdhfb.interaction ?? interactionDefaults) as InteractionConfigInput),
    onsite_u: -4.0,
    nearest_neighbor_v: -2.5,
    pairing_channel: "bond_d",
  };
  tdhfb.initial_state = {
    ...((tdhfb.initial_state ?? initialStateDefaults) as InitialStateConfigInput),
    seed_pairing: 0.2,
  };
  tdhfb.observables = ["density", "energy", "pairing", "pairing_s", "pairing_d"];

  const kbe = cloneConfig(tdhfb);
  kbe.name = "square-4x4-bond-d-kbe-hfb";
  kbe.solver = "kbe_hfb";

  return [createHiggsDemoPreset(), oneBody, tdhfb, kbe];
}

export function cloneConfig(config: PresetConfig | SimulationConfigInput): SimulationConfigInput {
  return JSON.parse(JSON.stringify(config)) as SimulationConfigInput;
}

export function describePreset(config: ConfigLike): PresetDescriptor {
  if (config.name === HIGGS_DEMO_PRESET_NAME) {
    return {
      title: "Higgs Demo draft",
      category: "Demo preset",
      intendedTab: "Single Job",
      summary: "A long-window `kbe_hfb + hfb + bond_d` draft with a Gaussian pulse and `pairing_d`-first readout.",
      scopeNote:
        "This is an illustrative demo preset, not a validated baseline. The pulse and observation window are tuned for smoother time-trace and FFT reading, but the numbers remain provisional.",
    };
  }

  if (config.solver === "kbe_hfb") {
    return {
      title: "Bond-d KBE-HFB scaffold",
      category: "Working baseline",
      intendedTab: "Single Job",
      summary: "A stored KBE-HFB draft for bond_d studies and contour inspection.",
      scopeNote:
        "Useful as the current Higgs-oriented entry point. Enriched preset metadata and explicit demo/baseline separation are still pending.",
    };
  }

  if (config.solver === "tdhfb") {
    return {
      title: "Bond-d TDHFB draft",
      category: "Mean-field pairing",
      intendedTab: "Single Job",
      summary: "A pairing-enabled mean-field draft for stationary states and equal-time checks.",
      scopeNote: "Use this for paired dynamics and for checking the equal-time bridge before KBE scattering closures.",
    };
  }

  return {
    title: "Noninteracting baseline",
    category: "Exact one-body baseline",
    intendedTab: "Single Job",
    summary: "Exact one-body propagation for transport and energy-work sanity checks.",
    scopeNote: "Use this as the clean benchmark surface for currents, density transport, and dt convergence.",
  };
}

export function selectWorkingBaselinePreset(
  presets: Array<PresetConfig | SimulationConfigInput>,
): PresetConfig | SimulationConfigInput {
  const fallbackPresets = createFallbackPresets();
  return (
    presets.find(
      (preset) =>
        preset.solver === "kbe_hfb" &&
        (preset.kbe?.self_energy ?? "hfb") === "hfb" &&
        (preset.interaction?.pairing_channel ?? "none") === "bond_d" &&
        preset.name !== HIGGS_DEMO_PRESET_NAME,
    ) ??
    presets.find((preset) => preset.solver === "tdhfb") ??
    presets[0] ??
    fallbackPresets.find(
      (preset) =>
        preset.solver === "kbe_hfb" &&
        (preset.kbe?.self_energy ?? "hfb") === "hfb" &&
        (preset.interaction?.pairing_channel ?? "none") === "bond_d" &&
        preset.name !== HIGGS_DEMO_PRESET_NAME,
    ) ??
    fallbackPresets[0]
  );
}

export function selectHiggsDemoPreset(
  presets: Array<PresetConfig | SimulationConfigInput>,
): PresetConfig | SimulationConfigInput {
  return (
    presets.find((preset) => preset.name === HIGGS_DEMO_PRESET_NAME) ??
    createHiggsDemoPreset()
  );
}

export function summarizeBaselineRelation(config: ConfigLike | null | undefined, baseline: ConfigLike): BaselineRelation {
  if (!config) {
    return {
      summary: "No run selected against the working baseline scaffold.",
      suggestedRole: "candidate",
      differences: [],
    };
  }

  const differences: DifferenceDescriptor[] = [];

  compareDifference(differences, "Solver", config.solver ?? "noninteracting", baseline.solver ?? "noninteracting", false);
  compareDifference(
    differences,
    "Self-energy",
    config.kbe?.self_energy ?? "hfb",
    baseline.kbe?.self_energy ?? "hfb",
    false,
  );
  compareDifference(
    differences,
    "Pairing channel",
    config.interaction?.pairing_channel ?? "none",
    baseline.interaction?.pairing_channel ?? "none",
    false,
  );
  compareDifference(
    differences,
    "Lattice",
    `${config.lattice?.nx ?? "?"}x${config.lattice?.ny ?? "?"}`,
    `${baseline.lattice?.nx ?? "?"}x${baseline.lattice?.ny ?? "?"}`,
    false,
  );
  compareDifference(
    differences,
    "dt",
    formatScalar(config.time?.dt),
    formatScalar(baseline.time?.dt),
    true,
  );
  compareDifference(
    differences,
    "Adaptive",
    String(config.adaptive?.enabled ?? false),
    String(baseline.adaptive?.enabled ?? false),
    true,
  );
  compareDifference(
    differences,
    "Drive Ax",
    formatScalar(config.drive?.amplitude_x),
    formatScalar(baseline.drive?.amplitude_x),
    false,
  );
  compareDifference(
    differences,
    "Drive frequency",
    formatScalar(config.drive?.frequency),
    formatScalar(baseline.drive?.frequency),
    false,
  );

  if (differences.length === 0) {
    return {
      summary: "Matches the working bond_d KBE-HFB baseline scaffold.",
      suggestedRole: "baseline",
      differences: [],
    };
  }

  const numericalOnly = differences.every((item) => item.numerical);
  return {
    summary: numericalOnly
      ? "Differs from the working baseline only through numerical controls."
      : "Differs from the working baseline through physics-facing settings.",
    suggestedRole: numericalOnly ? "numerical_check" : "candidate",
    differences: differences.map((item) => `${item.label}: ${item.current} vs ${item.baseline}`),
  };
}

export function describeComparisonDraft(
  config: ConfigLike,
  baseline: ConfigLike,
  baselineName: string | null,
): ComparisonDraftDescriptor {
  const relation = summarizeBaselineRelation(config, baseline);
  const comparisonKind = getComparisonKindFromRole(relation.suggestedRole);
  const comparisonKindLabel = getComparisonKindLabel(comparisonKind);
  const templateSeed = pickComparisonTemplate(relation.differences, comparisonKind);
  const baselineLabel = baselineName ?? baseline.name ?? "Working baseline scaffold";
  const draftLabel = config.name ?? "Untitled variant";
  const draftTrack = getTrackLabel(config);
  const baselineTrack = getTrackLabel(baseline);
  const variantIntent = describeVariantIntent(comparisonKind, baselineLabel, relation.summary, templateSeed);
  const reservedVariant = buildReservedVariant(comparisonKind, config, templateSeed);
  const differences = relation.differences.length > 0 ? relation.differences : ["No divergence from the working baseline yet."];

  return {
    comparisonKind,
    comparisonKindLabel,
    comparisonKindReason: describeComparisonKindReason(comparisonKind, relation.summary),
    variantIntent,
    templateSeed,
    baselineName: baselineLabel,
    planningBanner:
      comparisonKind === "regression"
        ? "Planning-only state. The draft still matches the working baseline scaffold, so the page is reserving compare structure before the first variant is added."
        : "Planning-only state. Comparison framing is staged locally, while backend-managed `job group` artifacts, child runs, and accepted/rejected notes are still pending.",
    emptyStateTitle: comparisonKind === "regression" ? "First Variant Not Added Yet" : "Child Runs Not Created Yet",
    emptyStateCopy:
      comparisonKind === "regression"
        ? "Use the left rail to push the draft away from the baseline before reading overlay or FFT compare surfaces."
        : "The summary is ready, but overlay, difference, FFT, and convergence panels stay empty until the future `job group` artifact exists.",
    emptyStateSteps: [
      "Load or edit the active variant in the left rail.",
      "Confirm `comparison_kind`, baseline, and variant intent in the summary table before launching anything.",
      "Wait for backend `job group` support before expecting child-run progress, accepted/rejected notes, or reusable compare artifacts.",
    ],
    summaryRows: [
      { label: "comparison_kind", value: comparisonKind, code: true },
      { label: "baseline", value: `${baselineLabel} (${baselineTrack})` },
      { label: "active_variant", value: `${draftLabel} (${draftTrack})` },
      { label: "variant_intent", value: variantIntent },
      { label: "template_seed", value: templateSeed },
      {
        label: "first_read",
        value: "Read the summary table first, then child-run state, and only then reserve overlay, difference, FFT, and convergence views.",
      },
    ],
    variants: [
      {
        key: "baseline",
        slot: "Baseline",
        label: baselineLabel,
        badges: ["Anchor", baselineTrack],
        summary: "Keep the compare artifact anchored to one explicit baseline instead of a floating selection of runs.",
        detail: "Baseline run id and child-run lineage remain backend responsibilities once `job group` support lands.",
        differences: [],
      },
      {
        key: "active",
        slot: "Active Variant",
        label: draftLabel,
        badges: ["Editing now", comparisonKindLabel],
        summary: variantIntent,
        detail: relation.summary,
        differences,
        active: true,
      },
      reservedVariant,
    ],
    planningSignals: [
      {
        title: "Artifact State",
        value: "No `job group` yet",
        copy: "This page is a design surface. Backend-managed compare artifacts and reusable group metadata are still pending.",
      },
      {
        title: "Child Runs",
        value: comparisonKind === "regression" ? "0 planned variants" : "Lineage pending",
        copy: "Progress, state rollups, and failure-aware summaries belong to the future group resource rather than to local ad hoc state.",
      },
      {
        title: "Baseline Link",
        value: baselineLabel,
        copy: "Baseline framing is fixed now so overlay and difference views will not inherit an ambiguous reference later.",
      },
      {
        title: "Decision Carry",
        value: "Reserved for compare artifact",
        copy: "Accepted or rejected judgments stay off the Single Job surface and will attach to the compare artifact once supported.",
      },
    ],
    reservedViews: [
      {
        title: "Overlay Compare",
        copy: "Primary plot slot for reading the same observable across all child runs once a managed group exists.",
      },
      {
        title: "Difference And Normalized Views",
        copy: "Use these only after the summary table and baseline framing are locked; they should not define the comparison by themselves.",
      },
      {
        title: "FFT Compare",
        copy: "Reserve this for spectrum-level reading after time-domain overlay is grounded in an explicit baseline and comparison kind.",
      },
      {
        title: "Convergence / Error Row",
        copy: "Keep numerical validation compares explicit here instead of blending them into physics-facing overlays.",
      },
    ],
    guardrails: [
      "Keep `comparison_kind` explicit so physics hypothesis compare and numerical validation compare do not blur together.",
      "`second_born` and `second_born_reference` must stay separate in variant labels, notes, and summary rows.",
      "Accepted or rejected judgments belong to the future compare artifact, not to the Single Job evidence surface.",
    ],
  };
}

function compareDifference(
  differences: DifferenceDescriptor[],
  label: string,
  current: string,
  baseline: string,
  numerical: boolean,
) {
  if (current !== baseline) {
    differences.push({ label, current, baseline, numerical });
  }
}

function formatScalar(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(4);
}

function getComparisonKindFromRole(role: SuggestedRunRole): ComparisonKind {
  if (role === "numerical_check") {
    return "numerical_validation";
  }
  if (role === "baseline") {
    return "regression";
  }
  return "physics_hypothesis";
}

function getComparisonKindLabel(kind: ComparisonKind): string {
  if (kind === "numerical_validation") {
    return "Numerical validation";
  }
  if (kind === "regression") {
    return "Regression";
  }
  return "Physics hypothesis";
}

function describeComparisonKindReason(kind: ComparisonKind, relationSummary: string): string {
  if (kind === "numerical_validation") {
    return `Current draft differs only through numerical controls. ${relationSummary}`;
  }
  if (kind === "regression") {
    return `Current draft still matches the baseline scaffold. ${relationSummary}`;
  }
  return `Current draft changes physics-facing settings against the working baseline. ${relationSummary}`;
}

function describeVariantIntent(
  kind: ComparisonKind,
  baselineName: string,
  relationSummary: string,
  templateSeed: string,
): string {
  if (kind === "numerical_validation") {
    return `Hold physics-facing settings fixed against ${baselineName} and use this variant to read numerical sensitivity through ${templateSeed}. ${relationSummary}`;
  }
  if (kind === "regression") {
    return `Keep ${baselineName} as the anchor and reserve the first sibling slot before treating this page as a real compare artifact. ${relationSummary}`;
  }
  return `Read this draft against ${baselineName} as a hypothesis-facing variant. Start from ${templateSeed} and keep solver, self-energy, and validation scope labels explicit.`;
}

function pickComparisonTemplate(differences: string[], kind: ComparisonKind): string {
  if (differences.some((item) => item.startsWith("Pairing channel:"))) {
    return "bond_s vs bond_d";
  }
  if (differences.some((item) => item.startsWith("Self-energy:"))) {
    return "hfb vs second_born vs second_born_reference";
  }
  if (differences.some((item) => item.startsWith("Drive Ax:"))) {
    return "drive amplitude discrete variants";
  }
  if (differences.some((item) => item.startsWith("dt:"))) {
    return "dt coarse vs fine";
  }
  if (differences.some((item) => item.startsWith("Adaptive:"))) {
    return "adaptive tolerance loose vs tight";
  }
  return kind === "numerical_validation" ? "dt coarse vs fine" : "bond_s vs bond_d";
}

function buildReservedVariant(
  kind: ComparisonKind,
  config: ConfigLike,
  templateSeed: string,
): ComparisonVariantDescriptor {
  if ((config.kbe?.self_energy ?? "hfb") === "second_born") {
    return {
      key: "reserved-reference",
      slot: "Reserved Sibling",
      label: "Reference path holdout",
      badges: ["Planning", "Keep separate"],
      summary: "Reserve an explicit `second_born_reference` sibling so prototype and reference paths do not collapse into one compare label.",
      detail: "This keeps the compare surface aligned with the documented prototype/reference split before group APIs arrive.",
      differences: ["Do not relabel heuristic `second_born` as literature-closed second Born."],
      planning: true,
    };
  }

  if ((config.kbe?.self_energy ?? "hfb") === "second_born_reference") {
    return {
      key: "reserved-prototype",
      slot: "Reserved Sibling",
      label: "Prototype contrast slot",
      badges: ["Planning", "Exploratory"],
      summary: "Keep a separate exploratory `second_born` sibling only if you need prototype/reference contrast, and do not merge their scope labels.",
      detail: "The compare artifact should be able to carry both paths without implying shared validation status.",
      differences: ["Prototype and reference scope must remain distinct in labels and summaries."],
      planning: true,
    };
  }

  if (kind === "numerical_validation") {
    return {
      key: "reserved-fine",
      slot: "Reserved Sibling",
      label: "Fine control holdout",
      badges: ["Planning", "Numerical"],
      summary: `Reserve a tighter sibling so ${templateSeed} reads as an explicit convergence check rather than a one-off tweak.`,
      detail: "Use this slot for a fine dt, tighter tolerance, or longer memory-window reference once job groups can manage child runs.",
      differences: ["Keep physics-facing settings fixed across the validation compare."],
      planning: true,
    };
  }

  return {
    key: "reserved-hypothesis",
    slot: "Reserved Sibling",
    label: "Hypothesis sibling slot",
    badges: ["Planning", "Template"],
    summary: `Reserve one more sibling so ${templateSeed} reads as a managed compare artifact instead of a two-run ad hoc overlay.`,
    detail: "The goal is to stage variant intent now and leave overlay mechanics to the future group resource.",
    differences: ["Keep baseline, variant intent, and future accepted/rejected notes attached to the compare artifact."],
    planning: true,
  };
}

function getTrackLabel(config: ConfigLike): string {
  const track = getSimulationTrack(config);
  return `${track.title} / ${track.statusLabel}`;
}
