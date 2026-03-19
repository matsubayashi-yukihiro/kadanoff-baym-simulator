type SimulationLike = {
  solver?: string | null;
  kbe?: {
    self_energy?: string | null;
  } | null;
};

export type TrackTone = "validated" | "partial" | "prototype" | "future";

export type TrackDescriptor = {
  key: string;
  title: string;
  statusLabel: string;
  tone: TrackTone;
};

export const TRACK_DESCRIPTORS: TrackDescriptor[] = [
  {
    key: "noninteracting",
    title: "Noninteracting One-Body Solver",
    statusLabel: "Validated",
    tone: "validated",
  },
  {
    key: "tdhfb",
    title: "TDHFB / BdG",
    statusLabel: "Partially Validated",
    tone: "partial",
  },
  {
    key: "kbe_hfb",
    title: "KBE + HFB",
    statusLabel: "Partially Validated",
    tone: "partial",
  },
  {
    key: "second_born",
    title: "KBE + second Born Prototype",
    statusLabel: "Prototype Only",
    tone: "prototype",
  },
  {
    key: "second_born_reference",
    title: "KBE + second Born Reference",
    statusLabel: "Validated Scope",
    tone: "validated",
  },
  {
    key: "full_contour",
    title: "Full Contour second Born",
    statusLabel: "Future Target",
    tone: "future",
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
