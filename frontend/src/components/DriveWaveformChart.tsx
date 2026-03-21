import type { DriveConfigInput } from "../lib/defaultConfig";

type DriveKind = "gaussian" | "sine" | "sech2" | "trapezoid";

type Props = {
  drive: DriveConfigInput;
  tFinal: number;
};

// SVG viewport constants
const W = 600;
const H = 160;
const ML = 42;
const MR = 12;
const MT = 12;
const MB = 28;
const PW = W - ML - MR;
const PH = H - MT - MB;
const N = 400;

const COLOR_X = "rgba(168,162,244,0.92)";
const COLOR_Y = "rgba(250,185,80,0.92)";
const COLOR_ENV = "rgba(168,162,244,0.30)";
const COLOR_GRID = "rgba(200,196,252,0.10)";
const COLOR_ZERO = "rgba(255,255,255,0.20)";
const COLOR_LABEL = "rgba(210,207,248,0.65)";
const FONT = "JetBrains Mono, monospace";

const DRIVE_LABELS: Record<DriveKind, string> = {
  gaussian: "Gaussian pulse",
  sine: "Pure sinusoidal",
  sech2: "Sech² pulse",
  trapezoid: "Trapezoid pulse",
};

function computeEnvelope(t: number, center: number, width: number, kind: DriveKind): number {
  const s = t - center;
  const w = Math.max(width, 1e-9);
  if (kind === "gaussian") return Math.exp(-0.5 * (s / w) ** 2);
  if (kind === "sech2") return 1.0 / Math.cosh(s / w) ** 2;
  if (kind === "trapezoid") {
    const k = 4.0;
    return 0.5 * (Math.tanh(k * (s / w + 1)) - Math.tanh(k * (s / w - 1)));
  }
  return 1.0; // sine: no envelope
}

function computeWaveform(
  ax: number, ay: number, freq: number, phase: number,
  center: number, width: number, kind: DriveKind, tFinal: number
): { valX: number[]; valY: number[]; envPos: number[]; envNeg: number[] } {
  const valX: number[] = [];
  const valY: number[] = [];
  const envPos: number[] = [];
  const envNeg: number[] = [];
  const maxAmp = Math.max(Math.abs(ax), Math.abs(ay));

  for (let i = 0; i < N; i++) {
    const t = (i / (N - 1)) * tFinal;
    const env = computeEnvelope(t, center, width, kind);
    const shifted = kind === "sine" ? t : t - center;
    const carrier = Math.sin(freq * shifted + phase);
    valX.push(ax * env * carrier);
    valY.push(ay * env * carrier);
    envPos.push(maxAmp * env);
    envNeg.push(-maxAmp * env);
  }
  return { valX, valY, envPos, envNeg };
}

function toX(i: number): number {
  return ML + (i / (N - 1)) * PW;
}

function toY(v: number, yMin: number, yMax: number): number {
  const range = yMax - yMin || 1;
  return MT + PH - ((v - yMin) / range) * PH;
}

function polylinePoints(values: number[], yMin: number, yMax: number): string {
  return values.map((v, i) => `${toX(i).toFixed(1)},${toY(v, yMin, yMax).toFixed(1)}`).join(" ");
}

function fmtVal(v: number): string {
  return Math.abs(v) < 0.001 ? "0" : v.toFixed(2).replace(/\.?0+$/, "");
}

export function DriveWaveformChart({ drive, tFinal }: Props) {
  const ax = drive.amplitude_x ?? 0;
  const ay = drive.amplitude_y ?? 0;
  const freq = drive.frequency ?? 0;
  const phase = drive.phase ?? 0;
  const center = drive.center ?? 0;
  const width = Math.max(drive.width ?? 1, 0.01);
  const kind: DriveKind = (drive.drive_type as DriveKind) ?? "gaussian";

  if (tFinal <= 0) {
    return (
      <div className="drive-waveform-shell">
        <p className="drive-waveform-hint">Set t_final &gt; 0 to preview waveform.</p>
      </div>
    );
  }

  const noDrive = ax === 0 && ay === 0;
  const maxAmp = noDrive ? 1 : Math.max(Math.abs(ax), Math.abs(ay));
  const absMax = maxAmp * 1.05;
  const yMin = -absMax;
  const yMax = absMax;

  const { valX, valY, envPos, envNeg } = noDrive
    ? { valX: Array(N).fill(0), valY: Array(N).fill(0), envPos: Array(N).fill(0), envNeg: Array(N).fill(0) }
    : computeWaveform(ax, ay, freq, phase, center, width, kind, tFinal);

  const gridFracs = [0.25, 0.5, 0.75];
  const yZero = toY(0, yMin, yMax);
  const xRight = ML + PW;
  const yTop = MT;
  const yBot = MT + PH;

  const showEnvelope = kind !== "sine" && !noDrive;

  return (
    <div className="drive-waveform-shell">
      <div className="drive-waveform-kind-label">{DRIVE_LABELS[kind]}</div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="drive-waveform-svg"
        aria-label="Vector potential waveform preview"
      >
        <rect x={0} y={0} width={W} height={H} rx={6} fill="#0f1722" stroke="rgba(168,162,244,0.18)" strokeWidth={1} />

        <clipPath id="drive-clip">
          <rect x={ML} y={MT} width={PW} height={PH} />
        </clipPath>

        {/* Grid lines */}
        {gridFracs.map((frac, gi) => {
          const yPos = toY(absMax * (1 - 2 * frac), yMin, yMax);
          const yNeg = toY(-absMax * (1 - 2 * frac), yMin, yMax);
          return (
            <g key={gi}>
              <line x1={ML} y1={yPos} x2={xRight} y2={yPos} stroke={COLOR_GRID} strokeWidth={0.8} strokeDasharray="4 4" />
              <line x1={ML} y1={yNeg} x2={xRight} y2={yNeg} stroke={COLOR_GRID} strokeWidth={0.8} strokeDasharray="4 4" />
            </g>
          );
        })}

        <rect x={ML} y={MT} width={PW} height={PH} fill="none" stroke="rgba(168,162,244,0.12)" strokeWidth={0.8} />

        {/* Zero line */}
        <line x1={ML} y1={yZero} x2={xRight} y2={yZero} stroke={COLOR_ZERO} strokeWidth={0.8} strokeDasharray="6 4" />

        {/* Envelope guides */}
        {showEnvelope && (
          <g clipPath="url(#drive-clip)">
            <polyline points={polylinePoints(envPos, yMin, yMax)} fill="none" stroke={COLOR_ENV} strokeWidth={1} strokeDasharray="5 4" />
            <polyline points={polylinePoints(envNeg, yMin, yMax)} fill="none" stroke={COLOR_ENV} strokeWidth={1} strokeDasharray="5 4" />
          </g>
        )}

        {/* A_y */}
        {ay !== 0 && (
          <polyline points={polylinePoints(valY, yMin, yMax)} fill="none" stroke={COLOR_Y} strokeWidth={1.4} clipPath="url(#drive-clip)" />
        )}
        {/* A_x */}
        {ax !== 0 && (
          <polyline points={polylinePoints(valX, yMin, yMax)} fill="none" stroke={COLOR_X} strokeWidth={1.4} clipPath="url(#drive-clip)" />
        )}

        {/* No drive label */}
        {noDrive && (
          <text x={ML + PW / 2} y={MT + PH / 2 + 1} textAnchor="middle" dominantBaseline="middle" fill="rgba(168,162,244,0.35)" fontSize={11} fontFamily={FONT}>
            No drive (amplitudes are zero)
          </text>
        )}

        {/* Y-axis labels */}
        <text x={ML - 4} y={yTop + 2} textAnchor="end" dominantBaseline="hanging" fill={COLOR_LABEL} fontSize={9} fontFamily={FONT}>{fmtVal(absMax)}</text>
        <text x={ML - 4} y={yZero} textAnchor="end" dominantBaseline="middle" fill={COLOR_LABEL} fontSize={9} fontFamily={FONT}>0</text>
        <text x={ML - 4} y={yBot} textAnchor="end" dominantBaseline="auto" fill={COLOR_LABEL} fontSize={9} fontFamily={FONT}>{fmtVal(-absMax)}</text>

        {/* X-axis labels */}
        <text x={ML} y={yBot + 5} textAnchor="start" dominantBaseline="hanging" fill={COLOR_LABEL} fontSize={9} fontFamily={FONT}>0</text>
        <text x={xRight} y={yBot + 5} textAnchor="end" dominantBaseline="hanging" fill={COLOR_LABEL} fontSize={9} fontFamily={FONT}>t = {fmtVal(tFinal)}</text>

        {/* A(t) axis title */}
        <text x={ML} y={yTop - 2} textAnchor="start" dominantBaseline="auto" fill={COLOR_LABEL} fontSize={9} fontFamily={FONT}>A(t)</text>
      </svg>

      {!noDrive && (
        <div className="drive-waveform-legend">
          {ax !== 0 && (
            <span className="drive-waveform-legend-item">
              <span className="drive-waveform-swatch" style={{ background: COLOR_X }} />
              A_x
            </span>
          )}
          {ay !== 0 && (
            <span className="drive-waveform-legend-item">
              <span className="drive-waveform-swatch" style={{ background: COLOR_Y }} />
              A_y
            </span>
          )}
          {showEnvelope && (
            <span className="drive-waveform-legend-item">
              <span className="drive-waveform-swatch" style={{ background: COLOR_ENV, border: "1px dashed rgba(168,162,244,0.5)" }} />
              envelope
            </span>
          )}
        </div>
      )}
    </div>
  );
}
