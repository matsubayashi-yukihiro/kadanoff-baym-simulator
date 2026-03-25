type HeatmapModel = {
  x: number[] | string[];
  y: number[];
  z: number[][];
  xAxisTitle: string;
  yAxisTitle: string;
  xTickVals?: number[];
  xTickText?: string[];
};

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every((item) => typeof item === "number" && Number.isFinite(item));
}

function isMatrix(value: unknown): value is number[][] {
  return Array.isArray(value) && value.every((row) => isNumberArray(row));
}

function isObservableSeries(value: unknown): value is { label: string; values: number[] } {
  if (!value || typeof value !== "object") return false;
  const raw = value as Record<string, unknown>;
  return typeof raw.label === "string" && isNumberArray(raw.values);
}

function transpose(matrix: number[][], rowCount: number, colCount: number): number[][] {
  return Array.from({ length: colCount }, (_, col) =>
    Array.from({ length: rowCount }, (_, row) => matrix[row][col]),
  );
}

export function normalizeRunFftPreviewPayload(payload: unknown) {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as Record<string, unknown>;
  if (typeof raw.name !== "string" || !isNumberArray(raw.time) || !Array.isArray(raw.series)) {
    return null;
  }
  if (!raw.series.every((series) => isObservableSeries(series))) {
    return null;
  }
  return raw;
}

export function normalizeKSpectralPayload(payload: unknown): HeatmapModel | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as Record<string, unknown>;

  // Legacy payload
  if (isMatrix(raw.spectrum) && isNumberArray(raw.omega)) {
    const rows = raw.spectrum.length;
    const cols = raw.omega.length;
    if (rows === 0 || cols === 0 || raw.spectrum.some((row) => row.length !== cols)) return null;
    const labels = Array.isArray(raw.k_labels) ? raw.k_labels.map(String) : [];
    const tickVals = isNumberArray(raw.k_indices) ? raw.k_indices : undefined;
    return {
      x: Array.from({ length: rows }, (_, i) => i),
      y: raw.omega,
      z: transpose(raw.spectrum, rows, cols),
      xAxisTitle: "k-path index",
      yAxisTitle: "omega",
      xTickVals: tickVals,
      xTickText: labels.length > 0 ? labels : undefined,
    };
  }

  // Current backend payload
  if (isMatrix(raw.intensity) && isNumberArray(raw.energy) && raw.k_surface && typeof raw.k_surface === "object") {
    const rows = raw.intensity.length;
    const cols = raw.energy.length;
    if (rows === 0 || cols === 0 || raw.intensity.some((row) => row.length !== cols)) return null;
    const kSurface = raw.k_surface as Record<string, unknown>;
    const tickVals = isNumberArray(kSurface.tick_positions) ? kSurface.tick_positions : undefined;
    const tickText = Array.isArray(kSurface.tick_labels) ? kSurface.tick_labels.map(String) : undefined;
    return {
      x: Array.from({ length: rows }, (_, i) => i),
      y: raw.energy,
      z: transpose(raw.intensity, rows, cols),
      xAxisTitle: "k-path index",
      yAxisTitle: "omega",
      xTickVals: tickVals,
      xTickText: tickText && tickText.length > 0 ? tickText : undefined,
    };
  }

  return null;
}

export function normalizeTrArpesPreviewPayload(payload: unknown): HeatmapModel | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as Record<string, unknown>;

  // Legacy payload
  if (isMatrix(raw.intensity) && isNumberArray(raw.omega) && isNumberArray(raw.probe_centers)) {
    const rows = raw.probe_centers.length;
    const cols = raw.omega.length;
    if (rows === 0 || cols === 0 || raw.intensity.length !== rows || raw.intensity.some((row) => row.length !== cols)) {
      return null;
    }
    return {
      x: raw.probe_centers,
      y: raw.omega,
      z: transpose(raw.intensity, rows, cols),
      xAxisTitle: "probe delay",
      yAxisTitle: "omega",
    };
  }

  // Current backend payload (run k-space preview encoded as k vs energy heatmap)
  if (isMatrix(raw.intensity) && isNumberArray(raw.energy) && raw.k_surface && typeof raw.k_surface === "object") {
    const rows = raw.intensity.length;
    const cols = raw.energy.length;
    if (rows === 0 || cols === 0 || raw.intensity.some((row) => row.length !== cols)) return null;
    const kSurface = raw.k_surface as Record<string, unknown>;
    const tickVals = isNumberArray(kSurface.tick_positions) ? kSurface.tick_positions : undefined;
    const tickText = Array.isArray(kSurface.tick_labels) ? kSurface.tick_labels.map(String) : undefined;
    return {
      x: Array.from({ length: rows }, (_, i) => i),
      y: raw.energy,
      z: transpose(raw.intensity, rows, cols),
      xAxisTitle: "k-path index",
      yAxisTitle: "omega",
      xTickVals: tickVals,
      xTickText: tickText && tickText.length > 0 ? tickText : undefined,
    };
  }

  return null;
}

export function normalizeSweepTrArpesHeatmapPayload(payload: unknown): HeatmapModel | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as Record<string, unknown>;
  if (!isMatrix(raw.intensity) || !isNumberArray(raw.energy) || !Array.isArray(raw.parameter_values)) {
    return null;
  }
  const rows = raw.parameter_values.length;
  const cols = raw.energy.length;
  if (rows === 0 || cols === 0 || raw.intensity.length !== rows || raw.intensity.some((row) => row.length !== cols)) {
    return null;
  }
  return {
    x: raw.parameter_values.map(String),
    y: raw.energy,
    z: transpose(raw.intensity, rows, cols),
    xAxisTitle: "sweep parameter",
    yAxisTitle: "omega",
  };
}
