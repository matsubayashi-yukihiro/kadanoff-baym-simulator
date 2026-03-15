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
