import type { ObservableResponse } from "../api/types";

export type SpectrumPreview = {
  data: ObservableResponse;
  dt: number;
  sampleCount: number;
  frequencyResolution: number;
  dominantFrequency: number | null;
  sourceSeriesLabel: string;
  meanSubtracted: boolean;
};

export function getDefaultSpectrumSeriesLabel(source: ObservableResponse | null | undefined): string | null {
  if (!source) {
    return null;
  }

  if (source.name.startsWith("pairing")) {
    const magnitudeSeries = source.series.find((series) => series.label === "magnitude");
    if (magnitudeSeries) {
      return magnitudeSeries.label;
    }
  }

  return source.series[0]?.label ?? null;
}

export function buildSpectrumPreview(
  source: ObservableResponse,
  seriesLabel: string | null | undefined,
): SpectrumPreview | null {
  const dt = inferUniformStep(source.time);
  if (dt === null) {
    return null;
  }

  const selectedSeries =
    source.series.find((series) => series.label === seriesLabel) ??
    source.series[0];

  if (!selectedSeries) {
    return null;
  }

  const sampleCount = Math.min(source.time.length, selectedSeries.values.length);
  if (sampleCount < 2) {
    return null;
  }

  const trimmedValues = selectedSeries.values.slice(0, sampleCount);
  const meanValue = trimmedValues.reduce((total, value) => total + value, 0) / sampleCount;
  const centeredValues = trimmedValues.map((value) => value - meanValue);
  const trimmedFrequencyCount = Math.floor(sampleCount / 2) + 1;
  const frequencies: number[] = [];
  const magnitudes: number[] = [];

  for (let frequencyIndex = 0; frequencyIndex < trimmedFrequencyCount; frequencyIndex += 1) {
    let real = 0;
    let imag = 0;

    for (let sampleIndex = 0; sampleIndex < sampleCount; sampleIndex += 1) {
      const angle = (-2 * Math.PI * frequencyIndex * sampleIndex) / sampleCount;
      real += centeredValues[sampleIndex] * Math.cos(angle);
      imag += centeredValues[sampleIndex] * Math.sin(angle);
    }

    frequencies.push(frequencyIndex / (sampleCount * dt));
    magnitudes.push(Math.sqrt(real * real + imag * imag) / sampleCount);
  }

  const dominantIndex =
    sampleCount > 2
      ? magnitudes.slice(1).reduce(
          (bestIndex, magnitude, index, entries) =>
            magnitude > entries[bestIndex] ? index : bestIndex,
          0,
        ) + 1
      : 0;

  return {
    data: {
      name: `${source.name}_fft_preview`,
      time: frequencies,
      series: [
        {
          label: `${selectedSeries.label} magnitude`,
          values: magnitudes,
        },
      ],
      units: source.units,
      metadata: {
        source_observable: source.name,
        source_series: selectedSeries.label,
        axis: "frequency",
        preprocessing: "mean_subtracted",
      },
    },
    dt,
    sampleCount,
    frequencyResolution: 1 / (sampleCount * dt),
    dominantFrequency: dominantIndex >= 0 ? frequencies[dominantIndex] ?? null : null,
    sourceSeriesLabel: selectedSeries.label,
    meanSubtracted: true,
  };
}

function inferUniformStep(times: number[]): number | null {
  if (times.length < 2) {
    return null;
  }

  const dt = times[1] - times[0];
  if (!Number.isFinite(dt) || dt <= 0) {
    return null;
  }

  for (let index = 2; index < times.length; index += 1) {
    const step = times[index] - times[index - 1];
    if (!Number.isFinite(step) || Math.abs(step - dt) > 1e-8) {
      return null;
    }
  }

  return dt;
}
