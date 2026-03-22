const OBSERVABLE_LABEL_MAP: Record<string, string> = {
  // Observable names
  pairing:          "Δ",
  pairing_s:        "Δ_s",
  pairing_d:        "Δ_d",
  density:          "n",
  energy:           "E",
  current_x:        "j_x",
  current_y:        "j_y",
  vector_potential: "A",
  // Series labels
  pairing_mean:     "Δ (mean)",
  pairing_s_mean:   "Δ_s (mean)",
  pairing_d_mean:   "Δ_d (mean)",
  density_mean:     "n (mean)",
  energy_mean:      "E (mean)",
  current_x_mean:   "j_x (mean)",
  current_y_mean:   "j_y (mean)",
};

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function formatNumber(value: unknown, maximumFractionDigits = 4): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return String(value ?? "-");
  }
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits,
  }).format(value);
}

export function formatLabel(value: string): string {
  if (Object.prototype.hasOwnProperty.call(OBSERVABLE_LABEL_MAP, value)) {
    return OBSERVABLE_LABEL_MAP[value];
  }
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatValue(value: unknown): string {
  if (typeof value === "number") {
    return formatNumber(value);
  }
  if (typeof value === "string" || typeof value === "boolean") {
    return String(value);
  }
  if (value === null || value === undefined) {
    return "-";
  }
  return JSON.stringify(value);
}
